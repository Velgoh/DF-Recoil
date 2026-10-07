// Delta Force Recoil Manager - C++ / Win32 rebuild (NieR themed)
// High-performance native port of "Delta Force - Yonah"
// Features: Native GDI+ dot extraction (OpenCV-free), NieR:Automata UI styling,
// real-time cross-validation window (DFCalibWnd), drag-and-drop & clipboard import,
// extended-mag tail compensation & decay clamp, Classic and Smooth modes, presets.ini persistence.

#define _CRT_SECURE_NO_WARNINGS
#define NOMINMAX
#include <windows.h>
#include <commdlg.h>
#include <shellapi.h>
#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <random>
#include <sstream>
#include <string>
#include <vector>
using std::max;
using std::min;
#include <gdiplus.h>

#pragma comment(lib, "gdiplus.lib")
#pragma comment(lib, "gdi32.lib")
#pragma comment(lib, "user32.lib")
#pragma comment(lib, "comdlg32.lib")
#pragma comment(lib, "winmm.lib")
#pragma comment(lib, "shell32.lib")

// ============================================================ data model
struct Dot { float x, y; };
struct Delta { double dx, dy; };
struct Pattern { std::vector<Delta> shots; Delta tail{0, 0}; bool classic = false; };

struct Preset {
    std::string name = "New Preset";
    std::string buildCode;
    double master = 1.0, vScale = 2.70, hScale = 2.92;
    double vDecay = 0.0, hDecay = 0.0;
    double decayStart = 0;            // shot index where decay begins counting
    double tailV = 100, tailH = 100;  // % applied to bullets past the last dot
    double rpm = 679, steps = 30, jitter = 0.35;
    double kickMult = 1.0, kickShots = 2;
    int hotkey = VK_F6;
    bool requireAds = true;
    int patternMode = 1;              // 0 = smooth, 1 = classic (identical to Python app)
    // calibration data (from screenshot)
    std::vector<Dot> green, grey;     // crop coordinates, as detected
    double vRatio = 1.0, hRatio = 1.0;
    double calKick = 1.0, calKickShots = 1;
    int matchPct = 0;
    std::string badge;
};

static double round2(double v) {
    double scaled = v * 100.0;
    double fl = std::floor(scaled);
    double diff = scaled - fl;
    if (std::abs(diff - 0.5) < 1e-9) {
        long long ifl = (long long)fl;
        return ((ifl % 2 == 0) ? fl : (fl + 1.0)) / 100.0;
    }
    return std::round(scaled) / 100.0;
}
static double medianOf(std::vector<double> v) {
    if (v.empty()) return 0;
    std::sort(v.begin(), v.end());
    size_t n = v.size();
    return n % 2 ? v[n / 2] : 0.5 * (v[n / 2 - 1] + v[n / 2]);
}
static std::vector<Dot> sortedByY(std::vector<Dot> d) {
    std::stable_sort(d.begin(), d.end(), [](const Dot& a, const Dot& b) { return a.y > b.y; });
    return d;
}
static int matchPercent(size_t a, size_t b) {
    if (a == 0 && b == 0) return 0;
    return (int)std::lround(100.0 * min(a, b) / max(a, b));
}

// ============================================================ calibration math (ported 1:1 from extractor.py)
static void compressionRatios(const std::vector<Dot>& grey, const std::vector<Dot>& green, double& vr, double& hr) {
    vr = hr = 1.0;
    if (grey.size() < 2 || green.size() < 2) return;
    auto sg = sortedByY(grey), sn = sortedByY(green);
    size_t K = min(sg.size(), sn.size());
    auto span = [&](const std::vector<Dot>& d, bool useX) {
        double lo = 1e9, hi = -1e9;
        for (size_t i = 0; i < K; i++) { double v = useX ? d[i].x : d[i].y; lo = min(lo, v); hi = max(hi, v); }
        return hi - lo;
    };
    double gh = span(sg, false), nh = span(sn, false);
    vr = gh > 5.0 ? nh / gh : 1.0;
    double gw = span(sg, true), nw = span(sn, true);
    if (gw > 5.0) hr = nw / gw;
    else if (nw > 5.0) hr = nw / 20.0;
    else hr = 1.0;
    vr = round2(std::clamp(vr, 0.10, 2.50));
    hr = round2(std::clamp(hr, 0.10, 2.50));
}

struct KickParams { double kick = 2.20; int shots = 6; double vScale = 2.70, hScale = 2.99; };
static KickParams kickParams(const std::vector<Dot>& dots) {
    KickParams kp;
    if (dots.size() < 2) return kp;
    auto s = sortedByY(dots);
    std::vector<Delta> d;
    for (size_t i = 0; i + 1 < s.size(); i++) d.push_back({s[i].x - s[i + 1].x, s[i].y - s[i + 1].y});
    size_t start = min<size_t>(4, d.size() - 1);
    std::vector<double> tail;
    for (size_t i = start; i < d.size(); i++) tail.push_back(d[i].dy);
    double steady = tail.empty() ? 7.5 : medianOf(tail);
    if (steady <= 0) steady = 7.5;
    double first = d[0].dy;
    double maxInit = d.size() > 1 ? max(first, d[1].dy) : first;
    kp.kick = round2(std::clamp(maxInit / steady, 1.0, 4.0));
    int ds = 6;
    for (size_t i = 1; i < d.size(); i++) if (d[i].dy <= 1.15 * steady) { ds = (int)i + 1; break; }
    kp.shots = std::clamp(ds, 1, 15);
    double minx = 1e9, maxx = -1e9, miny = 1e9, maxy = -1e9;
    for (auto& p : s) { minx = min(minx, (double)p.x); maxx = max(maxx, (double)p.x); miny = min(miny, (double)p.y); maxy = max(maxy, (double)p.y); }
    double sh = maxy - miny, sw = maxx - minx;
    kp.vScale = sh > 10 ? round2(std::clamp(2.70 * (sh / 222.0), 0.5, 6.0)) : 2.70;
    kp.hScale = sw > 5 ? round2(std::clamp(2.99 * (sw / 40.0), 0.5, 6.0)) : 2.99;
    return kp;
}

static double kickDivide(const Preset& p, int i, double dy) {
    if (p.calKick > 1.0 && p.calKickShots > 0 && i < p.calKickShots) {
        double f = 1.0 + (p.calKick - 1.0) * ((p.calKickShots - i) / p.calKickShots);
        dy /= f;
    }
    return dy;
}

// Classic = exactly what the Python app's generate_calibrated_pattern produced.
static Pattern classicPattern(const Preset& p) {
    Pattern pat; pat.classic = true;
    auto sg = sortedByY(p.grey), sn = sortedByY(p.green);
    auto& d = pat.shots;
    if (sg.size() >= 2) {
        for (size_t i = 0; i + 1 < sg.size(); i++) {
            double dx = (sg[i].x - sg[i + 1].x) * p.hRatio;
            double dy = kickDivide(p, (int)i, (sg[i].y - sg[i + 1].y) * p.vRatio);
            d.push_back({round2(dx), round2(dy)});
        }
        if (sn.size() > sg.size())
            for (size_t i = sg.size() - 1; i + 1 < sn.size(); i++)
                d.push_back({round2(sn[i].x - sn[i + 1].x), round2(sn[i].y - sn[i + 1].y)});
    } else if (sn.size() >= 2) {
        for (size_t i = 0; i + 1 < sn.size(); i++)
            d.push_back({round2(sn[i].x - sn[i + 1].x), round2(kickDivide(p, (int)i, sn[i].y - sn[i + 1].y))});
    }
    if (d.empty()) return pat;
    size_t tc = min(min<size_t>(5, max<size_t>(3, d.size())), d.size());
    double tx = 0, ty = 0;
    for (size_t i = d.size() - tc; i < d.size(); i++) { tx += d[i].dx; ty += d[i].dy; }
    pat.tail = {round2(tx / tc), round2(ty / tc)};
    return pat;
}

// Smooth = green dots, median filter (kills outlier dots) + binomial smoothing, tail from the last 12 shots' trend.
static Pattern smoothPattern(const Preset& p) {
    Pattern pat;
    auto dots = sortedByY(p.green);
    if (dots.size() < 3) return pat;
    size_t n = dots.size() - 1;
    std::vector<double> dx(n), dy(n);
    for (size_t i = 0; i < n; i++) { dx[i] = dots[i].x - dots[i + 1].x; dy[i] = dots[i].y - dots[i + 1].y; }
    auto med = [&](const std::vector<double>& s) {
        std::vector<double> o(s.size());
        for (int i = 0; i < (int)s.size(); i++) {
            std::vector<double> w;
            for (int k = -2; k <= 2; k++) w.push_back(s[std::clamp(i + k, 0, (int)s.size() - 1)]);
            o[i] = medianOf(w);
        }
        return o;
    };
    auto smooth = [&](const std::vector<double>& s) {
        static const double k[5] = {1, 4, 6, 4, 1};
        std::vector<double> o(s.size());
        for (int i = 0; i < (int)s.size(); i++) {
            double a = 0;
            for (int j = -2; j <= 2; j++) a += k[j + 2] * s[std::clamp(i + j, 0, (int)s.size() - 1)];
            o[i] = a / 16.0;
        }
        return o;
    };
    auto sdx = smooth(med(dx)), sdy = smooth(med(dy));
    for (size_t i = 0; i < n; i++) pat.shots.push_back({sdx[i], kickDivide(p, (int)i, sdy[i])});
    size_t tn = min<size_t>(12, n);
    double tx = 0, ty = 0;
    for (size_t i = n - tn; i < n; i++) { tx += sdx[i]; ty += sdy[i]; }
    pat.tail = {round2(tx / tn), round2(ty / tn)};
    return pat;
}

static std::string exeDir() {
    char p[MAX_PATH]; GetModuleFileNameA(nullptr, p, MAX_PATH);
    std::string s = p; return s.substr(0, s.find_last_of("\\/") + 1);
}

static const double kDefaultPattern[][2] = {
    {-0.59, 7.52}, {-1.63, 7.41}, {-1.68, 7.37}, {-1.01, 7.51}, {-0.95, 7.49}, {-0.87, 7.53}, {0.05, 7.58}, {-0.17, 7.58},
    {-0.06, 7.59}, {0.42, 7.56}, {0.17, 7.58}, {0.75, 7.54}, {1.37, 7.45}, {0.91, 7.53}, {1.62, 7.40}, {1.72, 7.39},
    {1.74, 7.36}, {2.13, 7.25}, {1.75, 7.38}, {2.46, 7.15}, {2.25, 7.22}, {2.67, 7.04}, {2.74, 6.99}, {2.39, 7.19},
    {3.23, 6.80}, {2.47, 7.17}, {2.85, 6.96}, {2.63, 7.09}, {2.73, 7.04}, {2.61, 7.09}};

static Pattern patternFor(const Preset& p) {
    Pattern a = p.patternMode == 1 ? classicPattern(p) : smoothPattern(p);
    if (a.shots.empty()) a = p.patternMode == 1 ? smoothPattern(p) : classicPattern(p);
    if (a.shots.empty()) {
        for (auto& d : kDefaultPattern) a.shots.push_back({d[0], d[1]});
        a.tail = a.shots.back();
    }
    return a;
}

static void savePatternJson(const Preset& p, const Pattern& pat) {
    std::string path = exeDir() + "pattern.json";
    std::ofstream f(path);
    if (!f) return;
    int delay = (int)std::lround(60000.0 / max(1.0, p.rpm));
    size_t magSize = max<size_t>(65, pat.shots.size());
    f << "{\n";
    f << "  \"description\": \"Delta Force Recoil Profile (Calibrated)\",\n";
    f << "  \"gun\": \"" << p.name << "\",\n";
    f << "  \"game\": \"Delta Force\",\n";
    f << "  \"magazine_size\": " << magSize << ",\n";
    f << "  \"base_fire_delay_ms\": " << delay << ",\n";
    f << "  \"shots\": [\n";
    for (size_t i = 0; i < magSize; i++) {
        Delta d = (i < pat.shots.size()) ? pat.shots[i] : pat.tail;
        f << "    {\n";
        f << "      \"bullet\": " << (i + 1) << ",\n";
        f << "      \"dx\": " << d.dx << ",\n";
        f << "      \"dy\": " << d.dy << "\n";
        f << "    }" << (i + 1 < magSize ? "," : "") << "\n";
    }
    f << "  ]\n";
    f << "}\n";
}

// Per-shot mouse movement:
// Solves 45-round magazine drift by clamping decay progression at the final pattern shot.
// Steady-state tail bullets (e.g. 30..45) maintain solid compensation, scaled by tailV and tailH.
static Delta shotMove(const Preset& P, const Pattern& pat, int idx) {
    bool tail = idx >= (int)pat.shots.size();
    Delta d = tail ? Delta{pat.tail.dx * P.tailH / 100.0, pat.tail.dy * P.tailV / 100.0} : pat.shots[idx];
    double kick = 1.0;
    if (idx < P.kickShots && P.kickShots > 0) kick = 1.0 + (P.kickMult - 1.0) * ((P.kickShots - idx) / P.kickShots);

    int lastPatternIdx = pat.shots.empty() ? 0 : ((int)pat.shots.size() - 1);
    int decayIdx = tail ? lastPatternIdx : idx;
    int di = max(0, decayIdx - (int)P.decayStart);
    double vf = std::clamp(1.0 - di * (P.vDecay / 100.0), 0.0, 3.0);
    double hf = std::clamp(1.0 - di * (P.hDecay / 100.0), 0.0, 3.0);
    return {d.dx * P.hScale * hf * P.master, d.dy * P.vScale * kick * vf * P.master};
}

// ============================================================ image loading + dot extraction (ported from extractor.py)
struct Image { int w = 0, h = 0; std::vector<BYTE> px; };  // BGRA, top-down

static bool bitmapToImage(Gdiplus::Bitmap& bmp, Image& img) {
    if (bmp.GetLastStatus() != Gdiplus::Ok) return false;
    img.w = (int)bmp.GetWidth(); img.h = (int)bmp.GetHeight();
    if (img.w <= 0 || img.h <= 0) return false;
    Gdiplus::Rect r(0, 0, img.w, img.h);
    Gdiplus::BitmapData bd;
    if (bmp.LockBits(&r, Gdiplus::ImageLockModeRead, PixelFormat32bppARGB, &bd) != Gdiplus::Ok) return false;
    img.px.resize((size_t)img.w * img.h * 4);
    for (int y = 0; y < img.h; y++)
        memcpy(&img.px[(size_t)y * img.w * 4], (const BYTE*)bd.Scan0 + (size_t)y * bd.Stride, (size_t)img.w * 4);
    bmp.UnlockBits(&bd);
    return true;
}
static bool loadImageFile(const wchar_t* path, Image& img) { Gdiplus::Bitmap b(path); return bitmapToImage(b, img); }

struct Extract { bool ok = false; std::string err; std::vector<Dot> grey, green; Image crop; };

using Kernel = std::vector<std::pair<int, int>>;
static Kernel ellipseKernel(int k) {  // same shape as cv2.getStructuringElement(MORPH_ELLIPSE)
    Kernel off;
    int r = k / 2, c = k / 2;
    double inv = 1.0 / (r * r);
    for (int i = 0; i < k; i++) {
        int dy = i - r, j1 = 0, j2 = 0;
        if (std::abs(dy) <= r) {
            int dx = (int)std::lround(c * std::sqrt((r * r - dy * dy) * inv));
            j1 = max(c - dx, 0); j2 = min(c + dx + 1, k);
        }
        for (int j = j1; j < j2; j++) off.push_back({j - c, dy});
    }
    return off;
}
static std::vector<int> morph(const std::vector<int>& s, int w, int h, const Kernel& k, bool takeMax) {
    std::vector<int> o(s.size());
    for (int y = 0; y < h; y++) for (int x = 0; x < w; x++) {
        int v = takeMax ? -1 : 256;
        for (auto& d : k) {
            int xx = x + d.first, yy = y + d.second;
            if (xx < 0 || yy < 0 || xx >= w || yy >= h) continue;
            int p = s[(size_t)yy * w + xx];
            v = takeMax ? max(v, p) : min(v, p);
        }
        o[(size_t)y * w + x] = v;
    }
    return o;
}
static std::vector<int> tophat(const std::vector<int>& s, int w, int h, int ksize) {
    Kernel k = ellipseKernel(ksize);
    auto op = morph(morph(s, w, h, k, false), w, h, k, true);
    std::vector<int> o(s.size());
    for (size_t i = 0; i < s.size(); i++) o[i] = max(0, s[i] - op[i]);
    return o;
}
static std::vector<double> gauss3(const std::vector<double>& s, int w, int h) {  // GaussianBlur((3,3), 0.8), reflect-101
    const double e = std::exp(-1.0 / (2 * 0.8 * 0.8));
    const double a = e / (1 + 2 * e), b = 1 / (1 + 2 * e);
    auto rf = [](int i, int n) { if (n == 1) return 0; if (i < 0) return -i; if (i >= n) return 2 * n - 2 - i; return i; };
    std::vector<double> t(s.size()), o(s.size());
    for (int y = 0; y < h; y++) for (int x = 0; x < w; x++)
        t[(size_t)y * w + x] = (a * s[(size_t)y * w + rf(x - 1, w)] + b * s[(size_t)y * w + x]) + a * s[(size_t)y * w + rf(x + 1, w)];
    for (int y = 0; y < h; y++) for (int x = 0; x < w; x++)
        o[(size_t)y * w + x] = b * t[(size_t)y * w + x] + a * (t[(size_t)rf(y - 1, h) * w + x] + t[(size_t)rf(y + 1, h) * w + x]);
    return o;
}
static std::vector<Dot> findPeaks(const std::vector<double>& bl, int w, int h, int xOff) {
    struct C { int x, y; double s; };
    std::vector<C> c;
    for (int y = 3; y < h - 3; y++) for (int x = 3; x < w - 3; x++) {
        double v = bl[(size_t)y * w + x];
        if (v < 7.0) continue;
        bool peak = true;
        for (int dy = -1; dy <= 1 && peak; dy++) for (int dx = -1; dx <= 1; dx++)
            if (bl[(size_t)(y + dy) * w + x + dx] > v) { peak = false; break; }
        if (peak) c.push_back({x, y, v});
    }
    std::stable_sort(c.begin(), c.end(), [](const C& a, const C& b) { return a.s > b.s; });
    std::vector<Dot> dots;
    for (auto& k : c) {
        float cx = (float)(k.x + xOff), cy = (float)k.y;
        bool close = false;
        for (auto& d : dots) if (std::hypot(cx - d.x, cy - d.y) < 4.8) { close = true; break; }
        if (!close) dots.push_back({cx, cy});
    }
    dots = sortedByY(dots);
    if (!dots.empty()) {
        std::vector<double> xs;
        for (auto& d : dots) xs.push_back(d.x);
        double mx = medianOf(xs);
        std::vector<Dot> f;
        for (auto& d : dots) if (std::fabs(d.x - mx) < 60) f.push_back(d);
        dots = f;
    }
    return dots;
}
static void hsvCv(int r, int g, int b, int& h, int& s, int& v) {  // OpenCV 8-bit HSV (H 0..180)
    int mx = max(r, max(g, b)), mn = min(r, min(g, b)), d = mx - mn;
    v = mx;
    s = mx ? (int)std::lround(d * 255.0 / mx) : 0;
    double hd = 0;
    if (d) {
        if (mx == r) hd = 60.0 * (g - b) / d;
        else if (mx == g) hd = 120.0 + 60.0 * (b - r) / d;
        else hd = 240.0 + 60.0 * (r - g) / d;
        if (hd < 0) hd += 360;
    }
    h = (int)std::lround(hd / 2.0);
}

static Extract extractDots(const Image& img) {
    Extract ex;
    int W = img.w, H = img.h;
    if (W < 60 || H < 60) { ex.err = "Image resolution is too small."; return ex; }
    int rt, rb, rl, rr;
    if ((double)W / H < 1.0 || W < 500) { rt = 0; rb = (int)(H * 0.88); rl = 0; rr = W; }
    else { rt = (int)(H * 0.15); rb = (int)(H * 0.86); rl = (int)(W * 0.56); rr = (int)(W * 0.94); }
    int cw = rr - rl, ch = rb - rt;
    ex.crop.w = cw; ex.crop.h = ch; ex.crop.px.resize((size_t)cw * ch * 4);
    for (int y = 0; y < ch; y++)
        memcpy(&ex.crop.px[(size_t)y * cw * 4], &img.px[((size_t)(rt + y) * W + rl) * 4], (size_t)cw * 4);
    auto P = [&](int x, int y) { return &ex.crop.px[((size_t)y * cw + x) * 4]; };
    int split = (int)(cw * 0.48);

    // left half: grey "Base Control" dots
    std::vector<int> gray((size_t)split * ch);
    std::vector<char> gm((size_t)split * ch);
    for (int y = 0; y < ch; y++) for (int x = 0; x < split; x++) {
        const BYTE* p = P(x, y);
        int b = p[0], g = p[1], r = p[2], hh, ss, vv;
        gray[(size_t)y * split + x] = (r * 4899 + g * 9617 + b * 1868 + 8192) >> 14;
        hsvCv(r, g, b, hh, ss, vv);
        gm[(size_t)y * split + x] = (hh >= 35 && hh <= 95 && ss > 50);
    }
    auto t5 = tophat(gray, split, ch, 5), t7 = tophat(gray, split, ch, 7), t11 = tophat(gray, split, ch, 11);
    std::vector<double> thl(gray.size());
    for (size_t i = 0; i < gray.size(); i++) thl[i] = gm[i] ? 0.0 : (double)max(t5[i], max(t7[i], t11[i]));
    ex.grey = findPeaks(gauss3(thl, split, ch), split, ch, 0);

    // right half: green "Current Loadout" dots
    int rw = cw - split;
    std::vector<int> sigInt((size_t)rw * ch, 0);
    for (int y = 0; y < ch; y++) for (int x = 0; x < rw; x++) {
        const BYTE* p = P(split + x, y);
        int b = p[0], g = p[1], r = p[2], hh, ss, vv;
        hsvCv(r, g, b, hh, ss, vv);
        if (hh >= 30 && hh <= 100 && ss >= 25 && vv >= 25 && g > r + 8)
            sigInt[(size_t)y * rw + x] = std::clamp(g - (r + b) / 2, 0, 255);
    }
    auto gt5 = tophat(sigInt, rw, ch, 5), gt11 = tophat(sigInt, rw, ch, 11);
    std::vector<double> gth((size_t)rw * ch, 0.0);
    for (size_t i = 0; i < sigInt.size(); i++)
        gth[i] = (double)max(sigInt[i], max(gt5[i], gt11[i]));
    ex.green = findPeaks(gauss3(gth, rw, ch), rw, ch, split);

    ex.ok = ex.green.size() >= 2 || ex.grey.size() >= 2;
    if (!ex.ok) ex.err = "No recoil dots detected on mannequin.";
    return ex;
}

// ============================================================ presets / persistence
static std::vector<Preset> g_presets;
static int g_sel = 0;
static std::string g_iniPath;

// Dots detected from the "aug myself" screenshot (DeltaForceClient-Win64-Shipping_dVjOqSulKa.png)
static const float kAugGreen[][2] = {
    {286, 354}, {288, 346}, {289, 338}, {289, 329}, {289, 321}, {289, 313}, {289, 305}, {288, 298},
    {287, 289}, {285, 281}, {284, 273}, {283, 265}, {280, 254}, {279, 249}, {276, 241}, {274, 234},
    {274, 226}, {270, 218}, {268, 210}, {267, 202}, {265, 194}, {264, 188}, {263, 179}, {263, 171},
    {262, 162}, {261, 154}, {261, 146}, {260, 139}, {259, 130}, {262, 122}};
static const float kAugGrey[][2] = {
    {115, 350}, {118, 337}, {120, 325}, {122, 313}, {122, 301}, {122, 289}, {121, 277}, {119, 265},
    {117, 254}, {114, 242}, {111, 231}, {109, 221}, {104, 207}, {100, 196}, {95, 184}, {91, 172},
    {87, 160}, {82, 149}, {79, 137}, {76, 129}, {76, 124}, {73, 114}, {72, 106}, {70, 91},
    {67, 80}, {67, 67}, {65, 56}, {63, 44}};

static void setDefaultDots(Preset& p) {
    p.green.clear(); p.grey.clear();
    for (auto& d : kAugGreen) p.green.push_back({d[0], d[1]});
    for (auto& d : kAugGrey) p.grey.push_back({d[0], d[1]});
    compressionRatios(p.grey, p.green, p.vRatio, p.hRatio);
    KickParams kp = kickParams(p.green);
    p.calKick = kp.kick; p.calKickShots = kp.shots;
    p.matchPct = matchPercent(p.grey.size(), p.green.size());
}

static std::vector<Preset> builtInDefaults() {
    std::vector<Preset> v;
    auto mk = [&](const char* n, const char* code, double rpm, double master, double vs, double hs, double vd, double hd,
                  double kick, double ks, double steps, double jit, double ds = 0, double tv = 100, double th = 100, int mode = 1) {
        Preset p; p.name = n; p.buildCode = code; p.rpm = rpm; p.master = master; p.vScale = vs; p.hScale = hs;
        p.vDecay = vd; p.hDecay = hd; p.kickMult = kick; p.kickShots = ks; p.steps = steps; p.jitter = jit;
        p.decayStart = ds; p.tailV = tv; p.tailH = th; p.patternMode = mode;
        setDefaultDots(p);
        v.push_back(p);
    };
    mk("aug myself", "AUG Assault Rifle-Warfare-6LFUAVS073PHD3H80H3R3a", 679, 3.0, 2.82, 2.24, 1.5, -1.5, 1.0, 2, 30, 1.5, 0, 90, 110, 0);
    mk("AUG", "AUG Assault Rifle-Warfare-6LFHGS4073PHD3H80H3R3", 679, 3.0, 2.70, 2.92, 1.3, 0.0, 1.0, 1, 30, 1.5, 0, 100, 100, 1);
    mk("aks74", "AUG Assault Rifle-Warfare-6LFHGS4073PHD3H80H3R3", 533, 0.41, 3.77, 1.79, 0.7, 10.0, 1.2, 3, 10, 0.35, 0, 100, 100, 1);
    mk("ptr32", "PTR-32 Assault Rifle-Warfare-6LG633O073PHD3H80H3R3", 632, 0.5, 2.88, 1.94, 0.7, -0.7, 1.0, 2, 30, 1.5, 0, 100, 100, 1);
    return v;
}

static std::string dotsToStr(const std::vector<Dot>& d) {
    std::ostringstream s;
    for (size_t i = 0; i < d.size(); i++) s << (i ? ";" : "") << d[i].x << "," << d[i].y;
    return s.str();
}
static std::vector<Dot> strToDots(const std::string& v) {
    std::vector<Dot> o; std::stringstream ss(v); std::string tok;
    while (std::getline(ss, tok, ';')) { float x, y; if (sscanf_s(tok.c_str(), "%f,%f", &x, &y) == 2) o.push_back({x, y}); }
    return o;
}

static void savePresets() {
    std::string tmp = g_iniPath + ".tmp";
    {
        std::ofstream f(tmp);
        if (!f) return;
        f << "[__config]\nactive=" << g_sel << "\n\n";
        for (auto& p : g_presets) {
            std::string cleanBadge = p.badge;
            std::replace(cleanBadge.begin(), cleanBadge.end(), '\n', ' ');
            f << "[" << p.name << "]\nbuild=" << p.buildCode << "\nrpm=" << p.rpm << "\nmaster=" << p.master
              << "\nvscale=" << p.vScale << "\nhscale=" << p.hScale << "\nvdecay=" << p.vDecay << "\nhdecay=" << p.hDecay
              << "\ndecaystart=" << p.decayStart << "\ntailv=" << p.tailV << "\ntailh=" << p.tailH
              << "\nsteps=" << p.steps << "\njitter=" << p.jitter << "\nkickmult=" << p.kickMult
              << "\nkickshots=" << p.kickShots << "\nhotkey=" << p.hotkey << "\nads=" << (p.requireAds ? 1 : 0)
              << "\nmode=" << p.patternMode << "\nvratio=" << p.vRatio << "\nhratio=" << p.hRatio
              << "\ncalkick=" << p.calKick << "\ncalkickshots=" << p.calKickShots << "\nmatch=" << p.matchPct
              << "\nbadge=" << cleanBadge << "\ngreen=" << dotsToStr(p.green) << "\ngrey=" << dotsToStr(p.grey) << "\n\n";
        }
    }
    if (!MoveFileExA(tmp.c_str(), g_iniPath.c_str(), MOVEFILE_REPLACE_EXISTING)) {
        CopyFileA(tmp.c_str(), g_iniPath.c_str(), FALSE);
        DeleteFileA(tmp.c_str());
    }
    if (!g_presets.empty() && g_sel >= 0 && g_sel < (int)g_presets.size()) {
        savePatternJson(g_presets[g_sel], patternFor(g_presets[g_sel]));
    }
}

static void loadPresets() {
    g_presets.clear();
    std::ifstream f(g_iniPath);
    if (!f) { g_presets = builtInDefaults(); savePresets(); return; }
    std::string line; Preset* cur = nullptr; bool cfg = false;
    std::vector<bool> hadRatio;
    while (std::getline(f, line)) {
        while (!line.empty() && (line.back() == '\r' || line.back() == '\n')) line.pop_back();
        if (line.empty()) continue;
        if (line[0] == '[' && line.back() == ']') {
            std::string nm = line.substr(1, line.size() - 2);
            if (nm == "__config") { cfg = true; cur = nullptr; }
            else { cfg = false; g_presets.emplace_back(); hadRatio.push_back(false); cur = &g_presets.back(); cur->name = nm; }
            continue;
        }
        size_t eq = line.find('=');
        if (eq == std::string::npos) continue;
        std::string k = line.substr(0, eq), v = line.substr(eq + 1);
        if (cfg) { if (k == "active") g_sel = atoi(v.c_str()); continue; }
        if (!cur) continue;
        double d = atof(v.c_str());
        if (k == "build") cur->buildCode = v;
        else if (k == "rpm") cur->rpm = d;
        else if (k == "delay" && d > 0) cur->rpm = 60000.0 / d;
        else if (k == "master") cur->master = d;
        else if (k == "vscale") cur->vScale = d;
        else if (k == "hscale") cur->hScale = d;
        else if (k == "vdecay") cur->vDecay = d;
        else if (k == "hdecay") cur->hDecay = d;
        else if (k == "decaystart") cur->decayStart = d;
        else if (k == "tailv") cur->tailV = d;
        else if (k == "tailh") cur->tailH = d;
        else if (k == "steps") cur->steps = d;
        else if (k == "jitter") cur->jitter = d;
        else if (k == "kickmult") cur->kickMult = d;
        else if (k == "kickshots") cur->kickShots = d;
        else if (k == "hotkey") cur->hotkey = (int)d;
        else if (k == "ads") cur->requireAds = d != 0;
        else if (k == "mode") cur->patternMode = (int)d;
        else if (k == "vratio") { cur->vRatio = d; hadRatio.back() = true; }
        else if (k == "hratio") cur->hRatio = d;
        else if (k == "calkick") cur->calKick = d;
        else if (k == "calkickshots") cur->calKickShots = d;
        else if (k == "match") cur->matchPct = (int)d;
        else if (k == "badge") cur->badge = v;
        else if (k == "green" || k == "dots") cur->green = strToDots(v);
        else if (k == "grey") cur->grey = strToDots(v);
    }
    if (g_presets.empty()) g_presets = builtInDefaults();
    for (size_t i = 0; i < g_presets.size(); i++) {
        Preset& p = g_presets[i];
        if (p.green.empty() && p.grey.empty()) setDefaultDots(p);
        else if (i < hadRatio.size() && !hadRatio[i]) {  // older file without calibration data
            if (p.grey.empty()) for (auto& d : kAugGrey) p.grey.push_back({d[0], d[1]});
            compressionRatios(p.grey, p.green, p.vRatio, p.hRatio);
            KickParams kp = kickParams(p.green.size() >= 2 ? p.green : p.grey);
            p.calKick = kp.kick; p.calKickShots = kp.shots;
            p.matchPct = matchPercent(p.grey.size(), p.green.size());
        }
    }
    g_sel = std::clamp(g_sel, 0, (int)g_presets.size() - 1);
    if (!g_presets.empty() && g_sel >= 0 && g_sel < (int)g_presets.size()) {
        savePatternJson(g_presets[g_sel], patternFor(g_presets[g_sel]));
    }
}

// ============================================================ engine
static CRITICAL_SECTION g_cs;
static Preset g_active;
static Pattern g_pattern;
static std::atomic<bool> g_enabled{false}, g_running{true};
static std::atomic<int> g_liveBullet{-1};
static HWND g_hwnd = nullptr;

static void syncEngine() {
    EnterCriticalSection(&g_cs);
    g_active = g_presets[g_sel];
    g_pattern = patternFor(g_active);
    LeaveCriticalSection(&g_cs);
}

static inline double nowSec() {
    static LARGE_INTEGER fq = [] { LARGE_INTEGER f; QueryPerformanceFrequency(&f); return f; }();
    LARGE_INTEGER c; QueryPerformanceCounter(&c);
    return (double)c.QuadPart / fq.QuadPart;
}
static void sleepUntil(double target) {
    for (;;) {
        double rem = target - nowSec();
        if (rem <= 0) return;
        if (rem > 0.002) Sleep(1); else YieldProcessor();
    }
}
static bool down(int vk) { return (GetAsyncKeyState(vk) & 0x8000) != 0; }
static bool guiFocused() {
    HWND fg = GetForegroundWindow();
    return fg && g_hwnd && (fg == g_hwnd || GetAncestor(fg, GA_ROOTOWNER) == g_hwnd || GetAncestor(fg, GA_ROOT) == g_hwnd);
}
static void moveMouse(int dx, int dy) {
    INPUT in{}; in.type = INPUT_MOUSE; in.mi.dx = dx; in.mi.dy = dy; in.mi.dwFlags = MOUSEEVENTF_MOVE;
    SendInput(1, &in, sizeof(INPUT));
}
// Cubic bezier easing (identical to Python app, p1 = 0.35, p2 = 0.75).
static double ease(double t) {
    t = std::clamp(t, 0.0, 1.0);
    const double p1 = 0.35, p2 = 0.75;
    return 3 * (1 - t) * (1 - t) * t * p1 + 3 * (1 - t) * t * t * p2 + t * t * t;
}

static DWORD WINAPI workerThread(LPVOID) {
    std::mt19937 rng{std::random_device{}()};
    bool hkPrev = false;
    while (g_running) {
        Preset P; Pattern pat;
        EnterCriticalSection(&g_cs); P = g_active; pat = g_pattern; LeaveCriticalSection(&g_cs);
        bool hk = down(P.hotkey);
        if (hk && !hkPrev) { g_enabled = !g_enabled; PostMessage(g_hwnd, WM_APP + 1, 0, 0); }
        hkPrev = hk;
        if (!g_enabled || guiFocused() || !down(VK_LBUTTON) || (P.requireAds && !down(VK_RBUTTON))) {
            g_liveBullet = -1;
            Sleep(2);
            continue;
        }
        double accX = 0, accY = 0;
        int idx = 0;
        auto firing = [&] { return g_running && g_enabled && down(VK_LBUTTON) && (!P.requireAds || down(VK_RBUTTON)) && !guiFocused(); };
        while (firing()) {
            EnterCriticalSection(&g_cs); P = g_active; pat = g_pattern; LeaveCriticalSection(&g_cs);
            g_liveBullet = idx;
            Delta m = shotMove(P, pat, idx);
            int steps = std::clamp((int)P.steps, 3, 50);
            double stepDur = (60.0 / max(60.0, P.rpm)) / steps;
            double t0 = nowSec(), prev = 0;
            std::normal_distribution<double> jn(0.0, P.jitter * 0.12 + 1e-9);
            bool stop = false;
            for (int s = 1; s <= steps; s++) {
                bool hkm = down(P.hotkey);
                if (hkm && !hkPrev) { g_enabled = !g_enabled; PostMessage(g_hwnd, WM_APP + 1, 0, 0); hkPrev = hkm; stop = true; break; }
                hkPrev = hkm;
                if (!firing()) { stop = true; break; }
                double e = ease((double)s / steps), dp = e - prev; prev = e;
                double stx = m.dx * dp, sty = m.dy * dp;
                if (P.jitter > 0) { stx += jn(rng); sty += jn(rng); }
                accX += stx; accY += sty;
                int mx = (int)accX, my = (int)accY;
                accX -= mx; accY -= my;
                if (mx || my) moveMouse(mx, my);
                sleepUntil(t0 + s * stepDur);
            }
            if (stop) break;
            idx++;
        }
        g_liveBullet = -1;
    }
    return 0;
}

// ============================================================ UI helpers (custom GDI & GDI+, Apple macOS Dark Mode)
struct SliderDef { const char* label; double Preset::*field; double lo, hi, step; const char* fmt; };
static const SliderDef kSliders[] = {
    {"MASTER SCALE", &Preset::master, 0.10, 6.0, 0.01, "%.2fx"},
    {"VERTICAL SCALE", &Preset::vScale, 0.10, 6.0, 0.01, "%.2fx"},
    {"HORIZONTAL SCALE", &Preset::hScale, 0.10, 6.0, 0.01, "%.2fx"},
    {"VERTICAL DECAY", &Preset::vDecay, -5.0, 10.0, 0.1, "%+.1f %%/shot"},
    {"HORIZONTAL DECAY", &Preset::hDecay, -5.0, 10.0, 0.1, "%+.1f %%/shot"},
    {"DECAY STARTS AT SHOT", &Preset::decayStart, 0, 45, 1, "%.0f"},
    {"INITIAL KICK", &Preset::kickMult, 1.0, 4.0, 0.05, "%.2fx"},
    {"KICK DURATION", &Preset::kickShots, 1, 15, 1, "%.0f shots"},
    {"FIRE RATE (RPM)", &Preset::rpm, 200, 1500, 1, "%.0f RPM"},
    {"SMOOTHING STEPS", &Preset::steps, 3, 50, 1, "%.0f steps"},
    {"JITTER", &Preset::jitter, 0.0, 1.5, 0.01, "+/- %.2f px"},
    {"TAIL VERTICAL (past last dot)", &Preset::tailV, 0, 300, 1, "%.0f %%"},
    {"TAIL SIDEWAYS (past last dot)", &Preset::tailH, -100, 300, 1, "%.0f %%"},
};
static const int kNumSliders = (int)(sizeof(kSliders) / sizeof(kSliders[0]));

// Slider column organization for Tab 0:
// Column 1: Sensitivity & Timing (6 sliders: Master, VScale, HScale, RPM, Steps, Jitter)
static const int kCol1Map[6] = {0, 1, 2, 8, 9, 10};
// Column 2: Stabilization & Dynamics (7 sliders: VDecay, HDecay, DecayStart, KickMult, KickShots, TailV, TailH)
static const int kCol2Map[7] = {3, 4, 5, 6, 7, 11, 12};

struct HK { const char* name; int vk; };
static const HK kHotkeys[] = {
    {"F1", VK_F1}, {"F2", VK_F2}, {"F3", VK_F3}, {"F4", VK_F4}, {"F5", VK_F5}, {"F6", VK_F6},
    {"F7", VK_F7}, {"F8", VK_F8}, {"F9", VK_F9}, {"F10", VK_F10}, {"F11", VK_F11}, {"F12", VK_F12},
    {"CapsLock", VK_CAPITAL}, {"Insert", VK_INSERT}, {"Delete", VK_DELETE}, {"Home", VK_HOME},
    {"End", VK_END}, {"PageUp", VK_PRIOR}, {"PageDown", VK_NEXT}, {"NumLock", VK_NUMLOCK},
    {"ScrollLock", VK_SCROLL}, {"Mouse4", VK_XBUTTON1}, {"Mouse5", VK_XBUTTON2}};
static const int kNumHotkeys = (int)(sizeof(kHotkeys) / sizeof(kHotkeys[0]));
static int hotkeyIndex(int vk) { for (int i = 0; i < kNumHotkeys; i++) if (kHotkeys[i].vk == vk) return i; return 5; }
static const char* hotkeyName(int vk) { return kHotkeys[hotkeyIndex(vk)].name; }

// Apple macOS Dark Mode Palette
static const COLORREF cBg = RGB(28, 28, 30);           // #1C1C1E Dark graphite background
static const COLORREF cHeader = RGB(22, 22, 24);       // #161618 Top nav & bottom bar
static const COLORREF cCard = RGB(44, 44, 46);         // #2C2C2E Card containers
static const COLORREF cCardInner = RGB(34, 34, 36);    // #222224 Inset surfaces (plot, edit, badges)
static const COLORREF cBorder = RGB(58, 58, 60);       // #3A3A3C Subtle borders & dividers
static const COLORREF cBorderHi = RGB(72, 72, 74);     // #48484A Hover / highlighted borders
static const COLORREF cBlue = RGB(10, 132, 255);       // #0A84FF Apple System Blue
static const COLORREF cBlueHover = RGB(64, 156, 255);  // #409CFF
static const COLORREF cGreen = RGB(48, 209, 88);       // #30D158 Apple System Green (Active/Sync)
static const COLORREF cOrange = RGB(255, 159, 10);     // #FF9F0A Apple System Orange (Tail/Standby)
static const COLORREF cRed = RGB(255, 69, 58);         // #FF453A Apple System Red (Destructive)
static const COLORREF cTextPrimary = RGB(255, 255, 255);   // #FFFFFF Crisp primary text
static const COLORREF cTextSecondary = RGB(220, 220, 225); // #DCDCE1 Secondary text
static const COLORREF cTextMuted = RGB(142, 142, 147);     // #8E8E93 Muted text / captions

static inline Gdiplus::Color gdColor(COLORREF c, BYTE alpha = 255) {
    return Gdiplus::Color(alpha, GetRValue(c), GetGValue(c), GetBValue(c));
}

static HFONT fTitle, fSection, fLabel, fBig, fSmall, fSmallBold, fBtn, fTab;
static HBRUSH g_brEdit;
static int g_dragSlider = -1, g_presetScroll = 0;
static bool g_naming = false, g_settingText = false;
static std::string g_status = "Ready.";
static HWND g_editBuild = nullptr;

// shared image source + last calibration (for cross-validation window)
static Image g_srcImage; static bool g_hasSrc = false; static std::string g_srcName;
static Extract g_lastExtract; static bool g_hasExtract = false;

// ------------------------------------------------------------ Layout Rectangles (Dynamic & Adaptive)
static int g_tab = 0; // 0 = Recoil Tuning, 1 = Pattern & Vision, 2 = Presets & Config
static int g_clientW = 1080, g_clientH = 620;

// Header rects
static RECT rcTabs[3]{};
static RECT rcHeaderPrev{};
static RECT rcHeaderPreset{};
static RECT rcHeaderNext{};
static RECT rcBanner{};

// Card boundaries
static RECT rcCardLeft{};
static RECT rcCardRight{};

// Tab 0: Recoil Tuning rects
static RECT rcSaveInTuning{};
static RECT rcReloadInTuning{};
static RECT rcSliderRows[kNumSliders]{};
static RECT rcSliderTracks[kNumSliders]{};

// Tab 1: Pattern & Vision rects
static RECT rcPlot{};
static RECT rcTelem{};
static RECT rcSelect{};
static RECT rcPaste{};
static RECT rcCalib{};
static RECT rcCross{};
static RECT rcMode{};
static RECT rcBadge{};

// Tab 2: Presets & Config rects
static const int PRESET_ROWS = 5, PRESET_H = 44;
static RECT rcPresets{};
static RECT rcNew{};
static RECT rcDel{};
static RECT rcSave{};
static RECT rcReset{};
static RECT rcReload{};
static RECT rcHotkey{};
static RECT rcAds{};
static RECT rcBuildEdit{};
static RECT rcCopyBuild{};
static RECT rcPasteBuild{};
static RECT rcGuide{};

static bool inRect(const RECT& r, int x, int y) { return x >= r.left && x < r.right && y >= r.top && y < r.bottom; }

static RECT sliderTrack(int i) {
    if (i >= 0 && i < kNumSliders) return rcSliderTracks[i];
    return RECT{0, 0, 0, 0};
}

static void updateLayout(int w, int h) {
    if (w <= 0 || h <= 0) return;
    g_clientW = w; g_clientH = h;

    // 1. Header Bar: y = 0..58
    int bannerW = 140;
    int bannerH = 36;
    int bannerY = 12;
    rcBanner = RECT{ w - 24 - bannerW, bannerY, w - 24, bannerY + bannerH };

    int nextW = 30;
    rcHeaderNext = RECT{ rcBanner.left - 8 - nextW, bannerY, rcBanner.left - 8, bannerY + bannerH };

    int presetW = 156;
    rcHeaderPreset = RECT{ rcHeaderNext.left - 4 - presetW, bannerY, rcHeaderNext.left - 4, bannerY + bannerH };

    int prevW = 30;
    rcHeaderPrev = RECT{ rcHeaderPreset.left - 4 - prevW, bannerY, rcHeaderPreset.left - 4, bannerY + bannerH };

    // Segmented Tabs
    int tabH = 36;
    int tabW = 140;
    int totalTabW = 3 * tabW;
    int tabX = (rcHeaderPrev.left + 230 - totalTabW) / 2;
    if (tabX < 236) tabX = 236;
    if (tabX + totalTabW > rcHeaderPrev.left - 10) tabX = max<int>(236, (int)(rcHeaderPrev.left - 10 - totalTabW));
    rcTabs[0] = RECT{ tabX, bannerY, tabX + tabW, bannerY + tabH };
    rcTabs[1] = RECT{ tabX + tabW, bannerY, tabX + 2 * tabW, bannerY + tabH };
    rcTabs[2] = RECT{ tabX + 2 * tabW, bannerY, tabX + 3 * tabW, bannerY + tabH };

    // 2. Footer Bar: height 34
    int footerTop = h - 34;

    // 3. Card Containers (Left & Right)
    int cardMargin = 20;
    int cardGap = 16;
    int cardTop = 62;
    int cardBottom = footerTop - 10;
    int cardW = max(380, (w - 2 * cardMargin - cardGap) / 2);
    rcCardLeft = RECT{ cardMargin, cardTop, cardMargin + cardW, cardBottom };
    rcCardRight = RECT{ rcCardLeft.right + cardGap, cardTop, w - cardMargin, cardBottom };

    // 4. Tab 0: Recoil Tuning
    int btnH = 36;
    int btnY = cardBottom - 12 - btnH;
    int btnMid = (rcCardLeft.left + rcCardLeft.right) / 2;
    rcSaveInTuning = RECT{ rcCardLeft.left + 20, btnY, btnMid - 6, btnY + btnH };
    rcReloadInTuning = RECT{ btnMid + 6, btnY, rcCardLeft.right - 20, btnY + btnH };

    // Column 1 Sliders (6 sliders)
    int col1Top = cardTop + 54;
    int col1AvailH = btnY - 8 - col1Top;
    int col1RowH = col1AvailH / 6;
    for (int r = 0; r < 6; r++) {
        int i = kCol1Map[r];
        int y = col1Top + r * col1RowH;
        rcSliderRows[i] = RECT{ rcCardLeft.left + 20, y, rcCardLeft.right - 20, y + col1RowH };
        rcSliderTracks[i] = RECT{ rcCardLeft.left + 20, y + 20, rcCardLeft.right - 20, y + 34 };
    }

    // Column 2 Sliders (7 sliders)
    int col2Top = cardTop + 54;
    int col2AvailH = cardBottom - 26 - col2Top; // reserve 26px for bottom hint text
    int col2RowH = col2AvailH / 7;
    for (int r = 0; r < 7; r++) {
        int i = kCol2Map[r];
        int y = col2Top + r * col2RowH;
        rcSliderRows[i] = RECT{ rcCardRight.left + 20, y, rcCardRight.right - 20, y + col2RowH };
        rcSliderTracks[i] = RECT{ rcCardRight.left + 20, y + 20, rcCardRight.right - 20, y + 34 };
    }

    // 5. Tab 1: Pattern & Vision
    int plotTop = cardTop + 50;
    int plotH = min(250, (cardBottom - plotTop - 20) * 58 / 100);
    rcPlot = RECT{ rcCardLeft.left + 20, plotTop, rcCardLeft.right - 20, plotTop + plotH };
    rcTelem = RECT{ rcCardLeft.left + 20, rcPlot.bottom + 10, rcCardLeft.right - 20, cardBottom - 12 };

    int pvBtnTop = cardTop + 50;
    int pvHalfW = (rcCardRight.right - rcCardRight.left - 40 - 10) / 2;
    rcSelect = RECT{ rcCardRight.left + 20, pvBtnTop, rcCardRight.left + 20 + pvHalfW, pvBtnTop + 36 };
    rcPaste = RECT{ rcSelect.right + 10, pvBtnTop, rcCardRight.right - 20, pvBtnTop + 36 };
    rcCalib = RECT{ rcCardRight.left + 20, rcSelect.bottom + 10, rcCardRight.right - 20, rcSelect.bottom + 46 };
    rcCross = RECT{ rcCardRight.left + 20, rcCalib.bottom + 10, rcCardRight.left + 20 + pvHalfW, rcCalib.bottom + 46 };
    rcMode = RECT{ rcCross.right + 10, rcCalib.bottom + 10, rcCardRight.right - 20, rcCalib.bottom + 46 };
    rcBadge = RECT{ rcCardRight.left + 20, rcCross.bottom + 10, rcCardRight.right - 20, cardBottom - 12 };

    // 6. Tab 2: Presets & Config
    int prTop = cardTop + 50;
    rcPresets = RECT{ rcCardLeft.left + 20, prTop, rcCardLeft.right - 20, prTop + PRESET_ROWS * PRESET_H };
    int prBtnY1 = rcPresets.bottom + 10;
    int prThirdW = (rcCardLeft.right - rcCardLeft.left - 40 - 16) / 3;
    rcNew = RECT{ rcCardLeft.left + 20, prBtnY1, rcCardLeft.left + 20 + prThirdW, prBtnY1 + 34 };
    rcDel = RECT{ rcNew.right + 8, prBtnY1, rcNew.right + 8 + prThirdW, prBtnY1 + 34 };
    rcSave = RECT{ rcDel.right + 8, prBtnY1, rcCardLeft.right - 20, prBtnY1 + 34 };
    int prBtnY2 = prBtnY1 + 40;
    int prHalfW = (rcCardLeft.right - rcCardLeft.left - 40 - 10) / 2;
    rcReset = RECT{ rcCardLeft.left + 20, prBtnY2, rcCardLeft.left + 20 + prHalfW, prBtnY2 + 34 };
    rcReload = RECT{ rcReset.right + 10, prBtnY2, rcCardLeft.right - 20, prBtnY2 + 34 };

    int cfgTop = cardTop + 50;
    rcHotkey = RECT{ rcCardRight.left + 20, cfgTop, rcCardRight.right - 20, cfgTop + 36 };
    rcAds = RECT{ rcCardRight.left + 20, rcHotkey.bottom + 10, rcCardRight.right - 20, rcHotkey.bottom + 46 };
    int bldLblY = rcAds.bottom + 14;
    rcBuildEdit = RECT{ rcCardRight.left + 20, bldLblY + 20, rcCardRight.right - 20, bldLblY + 54 };
    int bldHalfW = (rcCardRight.right - rcCardRight.left - 40 - 10) / 2;
    rcCopyBuild = RECT{ rcCardRight.left + 20, rcBuildEdit.bottom + 10, rcCardRight.left + 20 + bldHalfW, rcBuildEdit.bottom + 44 };
    rcPasteBuild = RECT{ rcCopyBuild.right + 10, rcBuildEdit.bottom + 10, rcCardRight.right - 20, rcBuildEdit.bottom + 44 };
    rcGuide = RECT{ rcCardRight.left + 20, rcCopyBuild.bottom + 10, rcCardRight.right - 20, cardBottom - 12 };

    if (g_editBuild) {
        SetWindowPos(g_editBuild, nullptr,
                     rcBuildEdit.left + 6, rcBuildEdit.top + 6,
                     (rcBuildEdit.right - rcBuildEdit.left) - 12,
                     (rcBuildEdit.bottom - rcBuildEdit.top) - 12,
                     SWP_NOZORDER | SWP_NOACTIVATE);
    }
}

// ------------------------------------------------------------ GDI & GDI+ Drawing Helpers
static void text(HDC dc, const std::string& s, int x, int y, HFONT f, COLORREF c, UINT fmt = DT_LEFT) {
    SelectObject(dc, f); SetTextColor(dc, c); SetBkMode(dc, TRANSPARENT);
    RECT r{x, y, x + 1100, y + 60};
    if (fmt & DT_RIGHT) { r.left = x - 1100; r.right = x; }
    DrawTextA(dc, s.c_str(), -1, &r, fmt | DT_NOPREFIX | DT_SINGLELINE);
}
static void textBox(HDC dc, const std::string& s, RECT r, HFONT f, COLORREF c) {
    SelectObject(dc, f); SetTextColor(dc, c); SetBkMode(dc, TRANSPARENT);
    DrawTextA(dc, s.c_str(), -1, &r, DT_LEFT | DT_WORDBREAK | DT_NOPREFIX);
}
static void fillRect(HDC dc, RECT r, COLORREF c) {
    HBRUSH b = CreateSolidBrush(c); FillRect(dc, &r, b); DeleteObject(b);
}

static void addRoundRectPath(Gdiplus::GraphicsPath& path, float x, float y, float w, float h, float r) {
    float d = r * 2.0f;
    if (d > w) d = w;
    if (d > h) d = h;
    path.AddArc(x, y, d, d, 180, 90);
    path.AddArc(x + w - d, y, d, d, 270, 90);
    path.AddArc(x + w - d, y + h - d, d, d, 0, 90);
    path.AddArc(x, y + h - d, d, d, 90, 90);
    path.CloseFigure();
}

static void fillRoundRect(Gdiplus::Graphics& g, int x, int y, int w, int h, int radius, Gdiplus::Color color) {
    Gdiplus::GraphicsPath path;
    addRoundRectPath(path, (float)x, (float)y, (float)w, (float)h, (float)radius);
    Gdiplus::SolidBrush brush(color);
    g.FillPath(&brush, &path);
}

static void drawRoundRect(Gdiplus::Graphics& g, int x, int y, int w, int h, int radius, Gdiplus::Color color, float width = 1.0f) {
    Gdiplus::GraphicsPath path;
    addRoundRectPath(path, (float)x, (float)y, (float)w, (float)h, (float)radius);
    Gdiplus::Pen pen(color, width);
    g.DrawPath(&pen, &path);
}

static void pillButton(Gdiplus::Graphics& g, HDC dc, const RECT& r, const std::string& label,
                       COLORREF bgCol, COLORREF textCol, COLORREF borderCol, bool hasBorder = true, HFONT font = nullptr) {
    int w = r.right - r.left, h = r.bottom - r.top;
    int radius = min(14, h / 2);
    fillRoundRect(g, r.left, r.top, w, h, radius, gdColor(bgCol));
    if (hasBorder) {
        drawRoundRect(g, r.left, r.top, w, h, radius, gdColor(borderCol), 1.0f);
    }
    g.Flush();
    HFONT f = font ? font : fBtn;
    SelectObject(dc, f); SetTextColor(dc, textCol); SetBkMode(dc, TRANSPARENT);
    RECT tr = r;
    DrawTextA(dc, label.c_str(), -1, &tr, DT_CENTER | DT_VCENTER | DT_SINGLELINE | DT_NOPREFIX);
}

static void cardContainer(Gdiplus::Graphics& g, HDC dc, const RECT& r, const std::string& title, const std::string& subtitle) {
    int w = r.right - r.left, h = r.bottom - r.top;
    fillRoundRect(g, r.left, r.top, w, h, 12, gdColor(cCard));
    drawRoundRect(g, r.left, r.top, w, h, 12, gdColor(cBorder), 1.0f);
    g.Flush();
    if (!title.empty()) {
        text(dc, title, r.left + 20, r.top + 16, fSection, cTextPrimary);
    }
    if (!subtitle.empty()) {
        text(dc, subtitle, r.left + 20, r.top + 42, fSmall, cTextMuted);
    }
}

static void dotPen(HDC dc, int x, int y, int r, COLORREF c, int width, int style = PS_SOLID) {
    HPEN pn = CreatePen(style, width, c);
    HGDIOBJ op = SelectObject(dc, pn), ob = SelectObject(dc, GetStockObject(NULL_BRUSH));
    Ellipse(dc, x - r, y - r, x + r + 1, y + r + 1);
    SelectObject(dc, op); SelectObject(dc, ob); DeleteObject(pn);
}

static void polyline(HDC dc, const std::vector<POINT>& pts, COLORREF c, int width, bool dashed = false) {
    if (pts.size() < 2) return;
    LOGBRUSH lb{BS_SOLID, c, 0};
    HPEN pn = ExtCreatePen(PS_GEOMETRIC | (dashed ? PS_DASH : PS_SOLID) | PS_ENDCAP_ROUND, width, &lb, 0, nullptr);
    HGDIOBJ op = SelectObject(dc, pn);
    Polyline(dc, pts.data(), (int)pts.size());
    SelectObject(dc, op); DeleteObject(pn);
}

static double sliderValue(int i) { return g_presets[g_sel].*kSliders[i].field; }
static std::string sliderText(int i) {
    char b[64]; snprintf(b, sizeof b, kSliders[i].fmt, sliderValue(i));
    std::string s = b;
    if (kSliders[i].field == &Preset::rpm) { char r[40]; snprintf(r, sizeof r, "  (%.0f ms)", 60000.0 / sliderValue(i)); s += r; }
    return s;
}
static void setSlider(int i, int mouseX) {
    const SliderDef& d = kSliders[i]; RECT t = sliderTrack(i);
    double f = std::clamp((double)(mouseX - t.left) / (t.right - t.left), 0.0, 1.0);
    double v = std::round((d.lo + f * (d.hi - d.lo)) / d.step) * d.step;
    g_presets[g_sel].*d.field = std::clamp(v, d.lo, d.hi);
    syncEngine();
}
static void refreshBuildEdit() {
    if (!g_editBuild) return;
    g_settingText = true;
    SetWindowTextA(g_editBuild, g_presets[g_sel].buildCode.c_str());
    g_settingText = false;
}
static void selectPreset(int idx) {
    g_sel = std::clamp(idx, 0, (int)g_presets.size() - 1);
    syncEngine();
    refreshBuildEdit();
    g_status = "Loaded preset: " + g_presets[g_sel].name;
    if (g_hwnd) InvalidateRect(g_hwnd, nullptr, FALSE);
}

// ============================================================ main window painting
static void drawPlot(Gdiplus::Graphics& g, HDC dc) {
    fillRoundRect(g, rcPlot.left, rcPlot.top, rcPlot.right - rcPlot.left, rcPlot.bottom - rcPlot.top, 8, gdColor(cCardInner));
    drawRoundRect(g, rcPlot.left, rcPlot.top, rcPlot.right - rcPlot.left, rcPlot.bottom - rcPlot.top, 8, gdColor(cBorder), 1.0f);

    const Preset& P = g_presets[g_sel];
    Pattern pat = patternFor(P);

    std::vector<std::pair<double, double>> pts{{0, 0}};
    double cx = 0, cy = 0;
    for (int i = 0; i < 45; i++) { Delta m = shotMove(P, pat, i); cx += m.dx; cy += m.dy; pts.push_back({cx, cy}); }
    double minx = 1e9, maxx = -1e9, maxy = 1;
    for (auto& p : pts) { minx = min(minx, p.first); maxx = max(maxx, p.first); maxy = max(maxy, p.second); }
    double spanx = max(40.0, maxx - minx), spany = max(40.0, maxy);
    double sc = min((rcPlot.right - rcPlot.left - 40) / spanx, (rcPlot.bottom - rcPlot.top - 50) / spany);
    double ox = (rcPlot.left + rcPlot.right) / 2.0 - (minx + spanx / 2) * sc, oy = rcPlot.top + 16;
    int live = g_liveBullet;

    // Subtle crosshair origin
    Gdiplus::Pen penCross(gdColor(cBorder), 1.0f);
    g.DrawLine(&penCross, (float)ox - 8.0f, (float)oy, (float)ox + 8.0f, (float)oy);
    g.DrawLine(&penCross, (float)ox, (float)oy - 8.0f, (float)ox, (float)oy + 8.0f);

    // Trajectory polyline
    std::vector<Gdiplus::PointF> linePts;
    for (size_t i = 1; i < pts.size(); i++) {
        float x = (float)(ox + pts[i].first * sc), y = (float)(oy + pts[i].second * sc);
        linePts.push_back(Gdiplus::PointF(x, y));
    }
    if (linePts.size() >= 2) {
        Gdiplus::Pen penLine(gdColor(cBorderHi), 1.5f);
        g.DrawLines(&penLine, linePts.data(), (INT)linePts.size());
    }

    // Dots
    Gdiplus::SolidBrush brNormal(gdColor(cTextMuted));
    Gdiplus::SolidBrush brTail(gdColor(cOrange));
    Gdiplus::SolidBrush brLive(gdColor(cGreen));
    Gdiplus::SolidBrush brLiveInner(gdColor(cTextPrimary));
    Gdiplus::Pen penNormal(gdColor(cBorder), 1.0f);
    Gdiplus::Pen penTail(gdColor(cOrange), 1.0f);
    Gdiplus::Pen penLiveGlow(Gdiplus::Color(100, 48, 209, 88), 3.0f);

    for (int i = 1; i < (int)pts.size(); i++) {
        float x = (float)(ox + pts[i].first * sc), y = (float)(oy + pts[i].second * sc);
        bool tail = i > (int)pat.shots.size();
        bool cur = (i - 1 == live && live >= 0);

        if (cur) {
            g.DrawEllipse(&penLiveGlow, x - 9.0f, y - 9.0f, 18.0f, 18.0f);
            g.FillEllipse(&brLive, x - 6.0f, y - 6.0f, 12.0f, 12.0f);
            g.FillEllipse(&brLiveInner, x - 2.5f, y - 2.5f, 5.0f, 5.0f);
        } else if (tail) {
            g.FillEllipse(&brTail, x - 4.0f, y - 4.0f, 8.0f, 8.0f);
            g.DrawEllipse(&penTail, x - 4.0f, y - 4.0f, 8.0f, 8.0f);
        } else {
            g.FillEllipse(&brNormal, x - 4.0f, y - 4.0f, 8.0f, 8.0f);
            g.DrawEllipse(&penNormal, x - 4.0f, y - 4.0f, 8.0f, 8.0f);
        }
    }
    g.Flush();

    // Legend
    text(dc, "● Base dots    ● Tail (45-mag)    ● Live bullet", rcPlot.left + 16, rcPlot.bottom - 24, fSmall, cTextMuted);
}

static void paint(HDC dc, RECT cr) {
    Gdiplus::Graphics g(dc);
    g.SetSmoothingMode(Gdiplus::SmoothingModeAntiAlias);
    g.SetTextRenderingHint(Gdiplus::TextRenderingHintClearTypeGridFit);

    // 1. Base dark background
    fillRect(dc, cr, cBg);

    // 2. Header Bar
    fillRect(dc, RECT{0, 0, cr.right, 58}, cHeader);
    HPEN penSep = CreatePen(PS_SOLID, 1, cBorder);
    HGDIOBJ opSep = SelectObject(dc, penSep);
    MoveToEx(dc, 0, 58, nullptr);
    LineTo(dc, cr.right, 58);
    SelectObject(dc, opSep);
    DeleteObject(penSep);

    // Left Title
    text(dc, "DF-RECOIL", 24, 14, fTitle, cTextPrimary);
    text(dc, "macOS Dark Edition · C++ Native", 25, 40, fSmall, cTextMuted);

    // Center: Segmented Tab Control
    fillRoundRect(g, rcTabs[0].left - 2, rcTabs[0].top - 2, (rcTabs[2].right - rcTabs[0].left) + 4, (rcTabs[0].bottom - rcTabs[0].top) + 4, 8, gdColor(cCardInner));
    drawRoundRect(g, rcTabs[0].left - 2, rcTabs[0].top - 2, (rcTabs[2].right - rcTabs[0].left) + 4, (rcTabs[0].bottom - rcTabs[0].top) + 4, 8, gdColor(cBorder), 1.0f);

    const char* tabNames[3] = {"Recoil Tuning", "Pattern & Vision", "Presets & Config"};
    for (int i = 0; i < 3; i++) {
        bool active = (g_tab == i);
        if (active) {
            fillRoundRect(g, rcTabs[i].left, rcTabs[i].top, rcTabs[i].right - rcTabs[i].left, rcTabs[i].bottom - rcTabs[i].top, 6, gdColor(cBlue));
        }
        g.Flush();
        SelectObject(dc, fTab);
        SetTextColor(dc, active ? cTextPrimary : cTextMuted);
        SetBkMode(dc, TRANSPARENT);
        RECT tr = rcTabs[i];
        DrawTextA(dc, tabNames[i], -1, &tr, DT_CENTER | DT_VCENTER | DT_SINGLELINE | DT_NOPREFIX);
    }

    // Right: Quick Preset Switcher
    pillButton(g, dc, rcHeaderPrev, "◄", cCard, cTextSecondary, cBorder, true, fBtn);
    std::string curPresetName = g_presets.empty() ? "" : g_presets[g_sel].name;
    pillButton(g, dc, rcHeaderPreset, curPresetName, cCard, cTextPrimary, cBorder, true, fBtn);
    pillButton(g, dc, rcHeaderNext, "►", cCard, cTextSecondary, cBorder, true, fBtn);

    // Master Enable / Standby Pill
    const Preset& P = g_presets[g_sel];
    char bannerText[64];
    snprintf(bannerText, sizeof bannerText, "%s (%s)", g_enabled ? "● ACTIVE" : "○ STANDBY", hotkeyName(P.hotkey));
    if (g_enabled) {
        pillButton(g, dc, rcBanner, bannerText, cGreen, RGB(0, 0, 0), cGreen, false, fBtn);
    } else {
        pillButton(g, dc, rcBanner, bannerText, cCard, cTextMuted, cBorder, true, fBtn);
    }

    // 3. Tab Contents
    if (g_tab == 0) {
        // Tab 0: Recoil Tuning
        cardContainer(g, dc, rcCardLeft, "SENSITIVITY & TIMING", "Core weapon scaling & fire-rate response");
        cardContainer(g, dc, rcCardRight, "STABILIZATION & DYNAMICS", "Recoil decay, kick damping & 45-mag tail");

        // Column 1 Sliders
        for (int r = 0; r < 6; r++) {
            int i = kCol1Map[r];
            RECT rowRc = rcSliderRows[i];
            text(dc, kSliders[i].label, rowRc.left, rowRc.top + 2, fLabel, cTextSecondary);
            text(dc, sliderText(i), rowRc.right, rowRc.top + 2, fLabel, cBlue, DT_RIGHT);
            RECT t = rcSliderTracks[i];
            fillRoundRect(g, t.left, t.top + 4, t.right - t.left, 6, 3, gdColor(cBorder));
            double f = (sliderValue(i) - kSliders[i].lo) / (kSliders[i].hi - kSliders[i].lo);
            int kx = t.left + (int)(f * (t.right - t.left));
            if (kx > t.left) fillRoundRect(g, t.left, t.top + 4, kx - t.left, 6, 3, gdColor(cBlue));
            Gdiplus::SolidBrush brThumb(gdColor(cTextPrimary));
            g.FillEllipse(&brThumb, (float)(kx - 8), (float)(t.top + 7 - 8), 16.0f, 16.0f);
            Gdiplus::Pen penThumb(Gdiplus::Color(255, 200, 200, 205), 1.0f);
            g.DrawEllipse(&penThumb, (float)(kx - 8), (float)(t.top + 7 - 8), 16.0f, 16.0f);
        }
        pillButton(g, dc, rcSaveInTuning, "SAVE PRESET", cBlue, cTextPrimary, cBlue, false, fBtn);
        pillButton(g, dc, rcReloadInTuning, "RELOAD FROM DISK", cCardInner, cTextSecondary, cBorder, true, fBtn);

        // Column 2 Sliders
        for (int r = 0; r < 7; r++) {
            int i = kCol2Map[r];
            RECT rowRc = rcSliderRows[i];
            text(dc, kSliders[i].label, rowRc.left, rowRc.top + 2, fLabel, cTextSecondary);
            text(dc, sliderText(i), rowRc.right, rowRc.top + 2, fLabel, cBlue, DT_RIGHT);
            RECT t = rcSliderTracks[i];
            fillRoundRect(g, t.left, t.top + 4, t.right - t.left, 6, 3, gdColor(cBorder));
            double f = (sliderValue(i) - kSliders[i].lo) / (kSliders[i].hi - kSliders[i].lo);
            int kx = t.left + (int)(f * (t.right - t.left));
            if (kx > t.left) fillRoundRect(g, t.left, t.top + 4, kx - t.left, 6, 3, gdColor(cBlue));
            Gdiplus::SolidBrush brThumb(gdColor(cTextPrimary));
            g.FillEllipse(&brThumb, (float)(kx - 8), (float)(t.top + 7 - 8), 16.0f, 16.0f);
            Gdiplus::Pen penThumb(Gdiplus::Color(255, 200, 200, 205), 1.0f);
            g.DrawEllipse(&penThumb, (float)(kx - 8), (float)(t.top + 7 - 8), 16.0f, 16.0f);
        }
        text(dc, "Decay counters gun stabilization. Tail applies past pattern dots (45-mag).", rcCardRight.left + 20, rcCardRight.bottom - 24, fSmall, cTextMuted);
    } else if (g_tab == 1) {
        // Tab 1: Pattern & Vision
        cardContainer(g, dc, rcCardLeft, "COMPENSATION TRAJECTORY", "Bézier path with steady-state tail & real-time telemetry");
        cardContainer(g, dc, rcCardRight, "MACHINE VISION AUTO-CALIBRATION", "Mannequin green & grey dot detection & compression math");

        drawPlot(g, dc);

        // Telemetry container
        fillRoundRect(g, rcTelem.left, rcTelem.top, rcTelem.right - rcTelem.left, rcTelem.bottom - rcTelem.top, 8, gdColor(cCardInner));
        drawRoundRect(g, rcTelem.left, rcTelem.top, rcTelem.right - rcTelem.left, rcTelem.bottom - rcTelem.top, 8, gdColor(cBorder), 1.0f);
        Pattern pat = patternFor(P);
        char tb[256];
        snprintf(tb, sizeof tb, "Loaded pattern: %d shots + tail  (%s Mode)", (int)pat.shots.size(), pat.classic ? "Classic" : "Smooth");
        text(dc, tb, rcTelem.left + 16, rcTelem.top + 14, fSmall, cTextSecondary);
        snprintf(tb, sizeof tb, "Compression: Vert x%.2f | Horiz x%.2f (%d%% Sync)", P.vRatio, P.hRatio, P.matchPct);
        text(dc, tb, rcTelem.left + 16, rcTelem.top + 38, fSmall, cTextSecondary);
        snprintf(tb, sizeof tb, "Steady drift: dx %+.2f, dy %+.2f  |  Decay: V %+.1f%%, H %+.1f%%", pat.tail.dx, pat.tail.dy, P.vDecay, P.hDecay);
        text(dc, tb, rcTelem.left + 16, rcTelem.top + 62, fSmall, cTextSecondary);
        int live = g_liveBullet;
        if (live >= 0) {
            snprintf(tb, sizeof tb, "● FIRING: BULLET %d / 45", live + 1);
            pillButton(g, dc, RECT{rcTelem.left + 16, rcTelem.top + 92, rcTelem.left + 260, rcTelem.top + 128}, tb, cGreen, RGB(0,0,0), cGreen, false, fBtn);
        } else {
            pillButton(g, dc, RECT{rcTelem.left + 16, rcTelem.top + 92, rcTelem.left + 280, rcTelem.top + 128}, "○ FIRING: IDLE (HOLD RMB + LMB)", cCard, cTextMuted, cBorder, true, fBtn);
        }

        // Right side buttons
        pillButton(g, dc, rcSelect, "SELECT SCREENSHOT", cCardInner, cTextSecondary, cBorder, true, fBtn);
        pillButton(g, dc, rcPaste, "PASTE (Ctrl+V)", cCardInner, cTextSecondary, cBorder, true, fBtn);
        pillButton(g, dc, rcCalib, "CALIBRATE & APPLY", cBlue, cTextPrimary, cBlue, false, fBtn);
        pillButton(g, dc, rcCross, "REVIEW DOTS (CROSS-CHECK)", cCardInner, cTextSecondary, cBorder, true, fBtn);
        pillButton(g, dc, rcMode, P.patternMode == 1 ? "MODE: CLASSIC" : "MODE: SMOOTH", cCardInner, cTextSecondary, cBorder, true, fBtn);

        // Status badge container
        fillRoundRect(g, rcBadge.left, rcBadge.top, rcBadge.right - rcBadge.left, rcBadge.bottom - rcBadge.top, 8, gdColor(cCardInner));
        drawRoundRect(g, rcBadge.left, rcBadge.top, rcBadge.right - rcBadge.left, rcBadge.bottom - rcBadge.top, 8, gdColor(cBorder), 1.0f);
        text(dc, "CALIBRATION STATUS & METRICS", rcBadge.left + 20, rcBadge.top + 16, fLabel, cTextPrimary);

        char sb[128];
        snprintf(sb, sizeof sb, "● %d%% PATTERN SYNCHRONIZATION", P.matchPct);
        pillButton(g, dc, RECT{rcBadge.left + 20, rcBadge.top + 46, rcBadge.right - 20, rcBadge.top + 88}, sb, cCard, (P.matchPct >= 80 ? cGreen : cOrange), cBorder, true, fBig);

        char rb[256];
        snprintf(rb, sizeof rb, "Vertical Ratio: x%.2f   ·   Horizontal Ratio: x%.2f", P.vRatio, P.hRatio);
        text(dc, rb, rcBadge.left + 20, rcBadge.top + 104, fSmall, cTextSecondary);
        snprintf(rb, sizeof rb, "Base Grey Dots: %d   ·   Loadout Green Dots: %d", (int)P.grey.size(), (int)P.green.size());
        text(dc, rb, rcBadge.left + 20, rcBadge.top + 130, fSmall, cTextSecondary);
        snprintf(rb, sizeof rb, "Initial Kick: %.2fx   ·   Kick Decay: %.0f shots", P.calKick, P.calKickShots);
        text(dc, rb, rcBadge.left + 20, rcBadge.top + 156, fSmall, cTextSecondary);

        if (g_hasSrc) {
            std::string srcLabel = "Source Image: " + g_srcName;
            text(dc, srcLabel, rcBadge.left + 20, rcBadge.top + 192, fSmall, cBlue);
        } else {
            text(dc, "Drag & drop a screenshot file or paste with Ctrl+V.", rcBadge.left + 20, rcBadge.top + 192, fSmall, cTextMuted);
        }
        std::string badgeDesc = P.badge.empty() ? "No calibration data active for this profile." : P.badge;
        textBox(dc, badgeDesc, RECT{rcBadge.left + 20, rcBadge.top + 220, rcBadge.right - 20, rcBadge.bottom - 10}, fSmall, cTextMuted);
    } else if (g_tab == 2) {
        // Tab 2: Presets & Config
        cardContainer(g, dc, rcCardLeft, "WEAPON PRESETS", "Custom profiles & recoil configurations");
        cardContainer(g, dc, rcCardRight, "CONTROLS & WEAPON BUILD CODE", "Global activation hotkey, ADS condition & Gunsmith codes");

        // Preset rows
        for (int i = 0; i < PRESET_ROWS; i++) {
            int idx = i + g_presetScroll;
            if (idx >= (int)g_presets.size()) break;
            RECT r{rcPresets.left, rcPresets.top + i * PRESET_H, rcPresets.right, rcPresets.top + (i + 1) * PRESET_H - 4};
            bool sel = (idx == g_sel);
            fillRoundRect(g, r.left, r.top, r.right - r.left, r.bottom - r.top, 6, gdColor(sel ? cBlue : cCardInner));
            drawRoundRect(g, r.left, r.top, r.right - r.left, r.bottom - r.top, 6, gdColor(sel ? cBlueHover : cBorder), 1.0f);
            g.Flush();
            std::string nm = (sel ? "✓  " : "    ") + g_presets[idx].name + ((sel && g_naming) ? "_" : "");
            text(dc, nm, r.left + 14, r.top + 10, fLabel, sel ? cTextPrimary : cTextSecondary);
        }
        if ((int)g_presets.size() > PRESET_ROWS) {
            char sb[64]; snprintf(sb, sizeof sb, "Scroll with wheel for more (%d total)", (int)g_presets.size());
            text(dc, sb, rcPresets.right - 6, rcPresets.bottom + 2, fSmall, cTextMuted, DT_RIGHT);
        }

        pillButton(g, dc, rcNew, "+ NEW PRESET", cCardInner, cTextSecondary, cBorder, true, fBtn);
        pillButton(g, dc, rcDel, "DELETE", cCardInner, cRed, cBorder, true, fBtn);
        pillButton(g, dc, rcSave, "SAVE", cBlue, cTextPrimary, cBlue, false, fBtn);
        pillButton(g, dc, rcReset, "RESET DEFAULTS", cCardInner, cTextSecondary, cBorder, true, fBtn);
        pillButton(g, dc, rcReload, "RELOAD ALL", cCardInner, cTextSecondary, cBorder, true, fBtn);
        text(dc, "Double-click or press F2 to rename preset. Enter or Esc to confirm.", rcCardLeft.left + 20, rcCardLeft.bottom - 24, fSmall, cTextMuted);

        // Right side: Controls
        pillButton(g, dc, rcHotkey, std::string("TOGGLE HOTKEY: ") + hotkeyName(P.hotkey) + "  (Click to cycle)", cCardInner, cTextPrimary, cBorder, true, fBtn);
        pillButton(g, dc, rcAds, P.requireAds ? "REQUIRE ADS (HOLD RMB): ON" : "REQUIRE ADS (HOLD RMB): OFF", cCardInner, P.requireAds ? cGreen : cTextMuted, cBorder, true, fBtn);

        text(dc, "GUNSMITH WEAPON BUILD CODE", rcCardRight.left + 20, rcAds.bottom + 14, fLabel, cTextSecondary);
        fillRoundRect(g, rcBuildEdit.left - 2, rcBuildEdit.top - 2, (rcBuildEdit.right - rcBuildEdit.left) + 4, (rcBuildEdit.bottom - rcBuildEdit.top) + 4, 6, gdColor(cCardInner));
        drawRoundRect(g, rcBuildEdit.left - 2, rcBuildEdit.top - 2, (rcBuildEdit.right - rcBuildEdit.left) + 4, (rcBuildEdit.bottom - rcBuildEdit.top) + 4, 6, gdColor(cBorder), 1.0f);
        pillButton(g, dc, rcCopyBuild, "COPY BUILD CODE", cCardInner, cTextSecondary, cBorder, true, fBtn);
        pillButton(g, dc, rcPasteBuild, "PASTE BUILD CODE", cCardInner, cTextSecondary, cBorder, true, fBtn);

        // Guide box
        fillRoundRect(g, rcGuide.left, rcGuide.top, rcGuide.right - rcGuide.left, rcGuide.bottom - rcGuide.top, 8, gdColor(cCardInner));
        drawRoundRect(g, rcGuide.left, rcGuide.top, rcGuide.right - rcGuide.left, rcGuide.bottom - rcGuide.top, 8, gdColor(cBorder), 1.0f);
        text(dc, "HOW TO USE DF-RECOIL:", rcGuide.left + 16, rcGuide.top + 14, fLabel, cTextPrimary);
        text(dc, "1. Select or create your weapon profile in this tab.", rcGuide.left + 16, rcGuide.top + 38, fSmall, cTextSecondary);
        char guide2[128];
        snprintf(guide2, sizeof guide2, "2. Press [%s] or click header pill to toggle recoil assistance.", hotkeyName(P.hotkey));
        text(dc, guide2, rcGuide.left + 16, rcGuide.top + 60, fSmall, cTextSecondary);
        text(dc, "3. Aim down sights (Hold RMB) and fire (Hold LMB) in game.", rcGuide.left + 16, rcGuide.top + 82, fSmall, cTextSecondary);
        text(dc, "4. Tune vertical/horizontal scale & decay in the Recoil Tuning tab.", rcGuide.left + 16, rcGuide.top + 104, fSmall, cTextSecondary);
        text(dc, "5. Import/export weapon codes directly to Delta Force Gunsmith.", rcGuide.left + 16, rcGuide.top + 126, fSmall, cTextSecondary);
    }

    // 4. Footer Bar
    int footerH = 34;
    int footerY = cr.bottom - footerH;
    fillRect(dc, RECT{0, footerY, cr.right, cr.bottom}, cHeader);
    HPEN penFoot = CreatePen(PS_SOLID, 1, cBorder);
    HGDIOBJ opFoot = SelectObject(dc, penFoot);
    MoveToEx(dc, 0, footerY, nullptr);
    LineTo(dc, cr.right, footerY);
    SelectObject(dc, opFoot);
    DeleteObject(penFoot);

    // Status dot
    Gdiplus::SolidBrush brStat(gdColor(g_enabled ? cGreen : cOrange));
    g.FillEllipse(&brStat, 24.0f, (float)(footerY + 13), 8.0f, 8.0f);
    g.Flush();
    text(dc, g_status, 38, footerY + 8, fSmall, cTextSecondary);

    char footText[128];
    snprintf(footText, sizeof footText, "Toggle: [%s]  |  ADS: [%s]  |  Tabs: [1] [2] [3]",
             hotkeyName(P.hotkey), P.requireAds ? "Hold RMB" : "Always");
    text(dc, footText, cr.right - 24, footerY + 8, fSmall, cTextMuted, DT_RIGHT);
}

// ============================================================ cross-validation window (Apple macOS Dark Mode styling)
static struct CalibWin {
    HWND hwnd = nullptr;
    std::vector<Dot> grey, green;
    double scale = 1.0;
    int imgX = 24, imgY = 120;
    RECT rcReset{}, rcCancel{}, rcConfirm{};
} g_cw;

static void applyCalibration(const std::vector<Dot>& green, const std::vector<Dot>& grey) {
    Preset& p = g_presets[g_sel];
    p.green = green; p.grey = grey;
    compressionRatios(grey, green, p.vRatio, p.hRatio);
    KickParams kp = kickParams(green.size() >= 2 ? green : grey);
    p.calKick = kp.kick; p.calKickShots = kp.shots;
    p.vScale = kp.vScale; p.hScale = kp.hScale; p.kickMult = kp.kick; p.kickShots = kp.shots;
    p.matchPct = matchPercent(grey.size(), green.size());
    int delay = (int)std::lround(60000.0 / max(1.0, p.rpm));
    char b[256];
    snprintf(b, sizeof b, "Calibrated %d shots @ %.0f RPM (%dms) | Ratio: Vx%.2f Hx%.2f (%d%% Sync)",
             (int)max(green.size(), grey.size()), p.rpm, delay, p.vRatio, p.hRatio, p.matchPct);
    p.badge = b;
    syncEngine();
    savePresets();
    savePatternJson(p, patternFor(p));
    snprintf(b, sizeof b, "Calibration applied to '%s': V scale %.2f, H scale %.2f, kick %.2fx / %d shots.",
             p.name.c_str(), p.vScale, p.hScale, p.kickMult, (int)p.kickShots);
    g_status = b;
    if (g_hwnd) InvalidateRect(g_hwnd, nullptr, FALSE);
}

static Preset g_presetBackup;
static bool g_hasBackup = false;

static void closeCalibWin() {
    if (!g_cw.hwnd) return;
    if (g_hasBackup) {
        g_presets[g_sel] = g_presetBackup;
        syncEngine();
        savePresets();
        savePatternJson(g_presets[g_sel], patternFor(g_presets[g_sel]));
        g_hasBackup = false;
        g_status = "Calibration cancelled. Presets restored.";
    }
    EnableWindow(g_hwnd, TRUE);
    DestroyWindow(g_cw.hwnd);
    g_cw.hwnd = nullptr;
    SetForegroundWindow(g_hwnd);
    InvalidateRect(g_hwnd, nullptr, FALSE);
}

static void paintCalib(HDC dc, RECT cr) {
    Gdiplus::Graphics g(dc);
    g.SetSmoothingMode(Gdiplus::SmoothingModeAntiAlias);

    fillRect(dc, cr, cBg);
    fillRect(dc, RECT{0, 0, cr.right, 106}, cHeader);
    HPEN penSep = CreatePen(PS_SOLID, 1, cBorder);
    HGDIOBJ opSep = SelectObject(dc, penSep);
    MoveToEx(dc, 0, 106, nullptr);
    LineTo(dc, cr.right, 106);
    SelectObject(dc, opSep);
    DeleteObject(penSep);

    size_t ng = g_cw.grey.size(), nn = g_cw.green.size();
    char b[256];
    snprintf(b, sizeof b, "SYNCHRONIZED: %d BASE / %d LOADOUT DOTS (%d%% MATCH)", (int)ng, (int)nn, matchPercent(ng, nn));
    text(dc, b, 24, 14, fBig, cTextPrimary);

    double vr = 1, hr = 1;
    if (ng >= 2 && nn >= 1) compressionRatios(g_cw.grey, g_cw.green, vr, hr);
    snprintf(b, sizeof b, "Compression Ratios: Vert x%.2f  |  Horiz x%.2f   (Base: %d, Loadout: %d)", vr, hr, (int)ng, (int)nn);
    text(dc, b, 24, 48, fLabel, cBlue);
    text(dc, "Click LEFT mannequin to add/remove grey dots; click RIGHT to add/remove green dots.", 24, 76, fSmall, cTextMuted);

    const Image& im = g_lastExtract.crop;
    int dw = (int)(im.w * g_cw.scale), dh = (int)(im.h * g_cw.scale);
    fillRoundRect(g, g_cw.imgX - 4, g_cw.imgY - 4, dw + 8, dh + 8, 6, gdColor(cCardInner));
    drawRoundRect(g, g_cw.imgX - 4, g_cw.imgY - 4, dw + 8, dh + 8, 6, gdColor(cBorder), 1.0f);

    BITMAPINFO bi{}; bi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER); bi.bmiHeader.biWidth = im.w;
    bi.bmiHeader.biHeight = -im.h; bi.bmiHeader.biPlanes = 1; bi.bmiHeader.biBitCount = 32; bi.bmiHeader.biCompression = BI_RGB;
    SetStretchBltMode(dc, HALFTONE);
    StretchDIBits(dc, g_cw.imgX, g_cw.imgY, dw, dh, 0, 0, im.w, im.h, im.px.data(), &bi, DIB_RGB_COLORS, SRCCOPY);

    auto S = [&](const Dot& d) { return POINT{g_cw.imgX + (LONG)(d.x * g_cw.scale), g_cw.imgY + (LONG)(d.y * g_cw.scale)}; };
    int r = max(3, (int)(5 * g_cw.scale));
    auto sg = sortedByY(g_cw.grey), sn = sortedByY(g_cw.green);
    std::vector<POINT> pg, pn;
    for (auto& d : sg) pg.push_back(S(d));
    for (auto& d : sn) pn.push_back(S(d));
    polyline(dc, pg, RGB(148, 163, 184), 1);
    polyline(dc, pn, RGB(48, 209, 88), 2);
    if (sg.size() >= 2 && !sn.empty()) {
        std::vector<POINT> pc;
        for (auto& d : sg) {
            Dot c{(float)(sn[0].x + (d.x - sg[0].x) * hr), (float)(sn[0].y - (sg[0].y - d.y) * vr)};
            pc.push_back(S(c));
        }
        polyline(dc, pc, RGB(10, 132, 255), 2, true);
    }
    for (auto& p : pg) dotPen(dc, p.x, p.y, r, RGB(255, 255, 255), 1, PS_DOT);
    for (auto& p : pn) dotPen(dc, p.x, p.y, r - 1, RGB(48, 209, 88), 2);

    pillButton(g, dc, g_cw.rcReset, "RESET TO AUTO-DETECTED", cCard, cTextSecondary, cBorder, true, fBtn);
    pillButton(g, dc, g_cw.rcCancel, "CANCEL", cCard, cTextSecondary, cBorder, true, fBtn);
    pillButton(g, dc, g_cw.rcConfirm, "CONFIRM & APPLY", cBlue, cTextPrimary, cBlue, false, fBtn);
    text(dc, "white = grey base dots   green = loadout dots   blue dashed = base scaled by ratios", 24,
         g_cw.rcReset.top - 24, fSmall, cTextMuted);
}

static LRESULT CALLBACK calibProc(HWND h, UINT m, WPARAM w, LPARAM l) {
    switch (m) {
    case WM_ERASEBKGND: return 1;
    case WM_PAINT: {
        PAINTSTRUCT ps; HDC dc = BeginPaint(h, &ps);
        RECT cr; GetClientRect(h, &cr);
        HDC mem = CreateCompatibleDC(dc); HBITMAP bm = CreateCompatibleBitmap(dc, cr.right, cr.bottom);
        HGDIOBJ old = SelectObject(mem, bm);
        paintCalib(mem, cr);
        BitBlt(dc, 0, 0, cr.right, cr.bottom, mem, 0, 0, SRCCOPY);
        SelectObject(mem, old); DeleteObject(bm); DeleteDC(mem);
        EndPaint(h, &ps); return 0;
    }
    case WM_LBUTTONDOWN: {
        int x = (short)LOWORD(l), y = (short)HIWORD(l);
        if (inRect(g_cw.rcReset, x, y)) {
            g_cw.grey = g_lastExtract.grey; g_cw.green = g_lastExtract.green;
        } else if (inRect(g_cw.rcCancel, x, y)) {
            closeCalibWin(); return 0;
        } else if (inRect(g_cw.rcConfirm, x, y)) {
            if (g_cw.green.size() < 2 && g_cw.grey.size() < 2) {
                MessageBoxA(h, "Need at least 2 dots to compute calibration.", "Calibration", MB_ICONWARNING);
                return 0;
            }
            g_hasBackup = false;
            applyCalibration(g_cw.green, g_cw.grey);
            closeCalibWin();
            return 0;
        } else {
            const Image& im = g_lastExtract.crop;
            double cx = (x - g_cw.imgX) / g_cw.scale, cy = (y - g_cw.imgY) / g_cw.scale;
            if (cx >= 0 && cy >= 0 && cx < im.w && cy < im.h) {
                int split = (int)(im.w * 0.48);
                auto& v = cx >= split ? g_cw.green : g_cw.grey;
                bool removed = false;
                for (size_t i = 0; i < v.size(); i++) {
                    if ((v[i].x - cx) * (v[i].x - cx) + (v[i].y - cy) * (v[i].y - cy) < 64) {
                        v.erase(v.begin() + i); removed = true; break;
                    }
                }
                if (!removed) v.push_back({(float)cx, (float)cy});
            }
        }
        InvalidateRect(h, nullptr, FALSE); return 0;
    }
    case WM_KEYDOWN: if (w == VK_ESCAPE) closeCalibWin(); return 0;
    case WM_CLOSE: closeCalibWin(); return 0;
    }
    return DefWindowProcW(h, m, w, l);
}

static void openCalibWin() {
    if (g_cw.hwnd) closeCalibWin();
    if (!g_hasExtract) return;
    const Image& im = g_lastExtract.crop;
    if (im.w <= 0 || im.h <= 0) return;

    if (!g_hasBackup) {
        g_presetBackup = g_presets[g_sel];
        g_hasBackup = true;
    }

    if (g_presets[g_sel].green.size() >= 2 || g_presets[g_sel].grey.size() >= 2) {
        g_cw.grey = g_presets[g_sel].grey;
        g_cw.green = g_presets[g_sel].green;
    } else {
        g_cw.grey = g_lastExtract.grey;
        g_cw.green = g_lastExtract.green;
    }

    // Dynamically size window to guarantee buttons are fully visible on screen
    RECT workArea{};
    SystemParametersInfoW(SPI_GETWORKAREA, 0, &workArea, 0);
    int workH = (workArea.bottom > workArea.top) ? (workArea.bottom - workArea.top) : 900;
    int workW = (workArea.right > workArea.left) ? (workArea.right - workArea.left) : 1600;

    int maxClientH = max(480, workH - 120);
    int maxClientW = max(700, workW - 120);
    int maxDH = max(200, maxClientH - 220);
    int maxDW = max(300, maxClientW - 80);

    double scaleH = (double)maxDH / max(1, im.h);
    double scaleW = (double)maxDW / max(1, im.w);
    g_cw.scale = std::clamp(min(scaleH, scaleW), 0.30, 2.0);

    int dw = (int)(im.w * g_cw.scale), dh = (int)(im.h * g_cw.scale);
    int cw = max(800, min(maxClientW, dw + 60));
    g_cw.imgX = (cw - dw) / 2;
    g_cw.imgY = 120;
    int btnY = g_cw.imgY + dh + 30;

    g_cw.rcReset = RECT{24, btnY, 24 + 260, btnY + 44};
    g_cw.rcConfirm = RECT{cw - 24 - 220, btnY, cw - 24, btnY + 44};
    g_cw.rcCancel = RECT{g_cw.rcConfirm.left - 12 - 130, btnY, g_cw.rcConfirm.left - 12, btnY + 44};

    int clientH = btnY + 56;
    RECT r{0, 0, cw, clientH};
    DWORD st = WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU;
    AdjustWindowRect(&r, st, FALSE);
    int ww = r.right - r.left, wh = r.bottom - r.top;

    RECT mr{};
    GetWindowRect(g_hwnd, &mr);
    int posX = mr.left + ((mr.right - mr.left) - ww) / 2;
    int posY = mr.top + ((mr.bottom - mr.top) - wh) / 2;
    if (posX < workArea.left) posX = workArea.left + 10;
    if (posY < workArea.top) posY = workArea.top + 10;
    if (posY + wh > workArea.bottom) posY = max(workArea.top, workArea.bottom - wh - 10);

    g_cw.hwnd = CreateWindowW(L"DFCalibWnd", L"Pattern Cross-Validation", st,
                              posX, posY, ww, wh, g_hwnd, nullptr, GetModuleHandle(nullptr), nullptr);
    EnableWindow(g_hwnd, FALSE);
    ShowWindow(g_cw.hwnd, SW_SHOW);
}

static void selectScreenshot();

static void runCalibration() {
    if (!g_hasSrc) {
        selectScreenshot();
        return;
    }
    Extract ex = extractDots(g_srcImage);
    if (!ex.ok) {
        std::string msg = ex.err.empty() ? "Calibration failed: no recoil dots detected." : ex.err;
        g_status = "Calibration error: " + msg;
        MessageBoxA(g_hwnd, msg.c_str(), "Calibration Failed", MB_ICONERROR);
        InvalidateRect(g_hwnd, nullptr, FALSE);
        return;
    }
    g_lastExtract = ex;
    g_hasExtract = true;
    applyCalibration(ex.green, ex.grey);
}

static void selectScreenshot() {
    wchar_t file[MAX_PATH] = L"";
    OPENFILENAMEW o{}; o.lStructSize = sizeof o; o.hwndOwner = g_hwnd; o.lpstrFile = file; o.nMaxFile = MAX_PATH;
    o.lpstrFilter = L"Image Files\0*.png;*.jpg;*.jpeg;*.bmp\0All\0*.*\0";
    wchar_t dir[MAX_PATH]; ExpandEnvironmentStringsW(L"%USERPROFILE%\\Pictures\\Screenshots", dir, MAX_PATH);
    o.lpstrInitialDir = dir; o.Flags = OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST;
    if (!GetOpenFileNameW(&o)) return;
    Image img;
    if (!loadImageFile(file, img)) { MessageBoxA(g_hwnd, "Could not open that image.", "Calibration", MB_ICONERROR); return; }
    g_srcImage = img; g_hasSrc = true;
    std::wstring wn = file; wn = wn.substr(wn.find_last_of(L"\\/") + 1);
    char nb[MAX_PATH]; WideCharToMultiByte(CP_ACP, 0, wn.c_str(), -1, nb, MAX_PATH, nullptr, nullptr);
    g_srcName = nb;
    runCalibration();
}

static void pasteScreenshot() {
    if (!OpenClipboard(g_hwnd)) return;
    Image img;
    bool ok = false;
    std::string srcName = "pasted from clipboard";

    // 1. Check for file list (CF_HDROP) e.g. copied from Explorer / Downloads
    if (IsClipboardFormatAvailable(CF_HDROP)) {
        HANDLE hDrop = GetClipboardData(CF_HDROP);
        if (hDrop) {
            wchar_t path[MAX_PATH] = L"";
            if (DragQueryFileW((HDROP)hDrop, 0, path, MAX_PATH)) {
                if (loadImageFile(path, img)) {
                    ok = true;
                    std::wstring wn = path;
                    wn = wn.substr(wn.find_last_of(L"\\/") + 1);
                    char nb[MAX_PATH];
                    WideCharToMultiByte(CP_ACP, 0, wn.c_str(), -1, nb, MAX_PATH, nullptr, nullptr);
                    srcName = nb;
                }
            }
        }
    }

    // 2. Direct Bitmap (CF_BITMAP / CF_DIB)
    if (!ok && (IsClipboardFormatAvailable(CF_BITMAP) || IsClipboardFormatAvailable(CF_DIB))) {
        HBITMAP hbm = (HBITMAP)GetClipboardData(CF_BITMAP);
        if (hbm) {
            Gdiplus::Bitmap bmp(hbm, nullptr);
            if (bitmapToImage(bmp, img)) {
                ok = true;
            }
        }
    }

    CloseClipboard();

    if (ok) {
        g_srcImage = img;
        g_hasSrc = true;
        g_srcName = srcName;
        g_status = "Pasted image (" + std::to_string(img.w) + "x" + std::to_string(img.h) + "). Auto-calibrating...";
        runCalibration();
    } else {
        g_status = "No image found on clipboard (copy an image or screenshot first).";
        InvalidateRect(g_hwnd, nullptr, FALSE);
    }
}

// ============================================================ preset actions
static std::string uniqueName(std::string base, int skip) {
    auto taken = [&](const std::string& n) {
        for (int i = 0; i < (int)g_presets.size(); i++)
            if (i != skip && g_presets[i].name == n) return true;
        return false;
    };
    if (base.empty()) base = "Preset";
    if (!taken(base)) return base;
    for (int k = 2;; k++) {
        std::string n = base + " (" + std::to_string(k) + ")";
        if (!taken(n)) return n;
    }
}

static void resetDefaults() {
    auto defs = builtInDefaults();
    Preset& p = g_presets[g_sel];
    std::string nm = p.name;
    Preset src = defs[0];
    for (auto& d : defs) if (d.name == nm) src = d;
    p = src; p.name = nm;
    syncEngine(); refreshBuildEdit(); savePresets();
    g_status = "Reset '" + nm + "' to defaults.";
    if (g_hwnd) InvalidateRect(g_hwnd, nullptr, FALSE);
}

static void reloadAll() {
    loadPresets();
    syncEngine(); refreshBuildEdit();
    g_status = "Reloaded presets from disk.";
    if (g_hwnd) InvalidateRect(g_hwnd, nullptr, FALSE);
}

// ============================================================ main window proc
static LRESULT CALLBACK wndProc(HWND h, UINT m, WPARAM w, LPARAM l) {
    switch (m) {
    case WM_CREATE: {
        SetTimer(h, 1, 60, nullptr);
        DragAcceptFiles(h, TRUE);
        RECT cr{}; GetClientRect(h, &cr);
        if (cr.right > 0 && cr.bottom > 0) updateLayout(cr.right, cr.bottom);
        g_editBuild = CreateWindowExW(0, L"EDIT", L"", WS_CHILD | ES_AUTOHSCROLL,
                                      rcBuildEdit.left + 6, rcBuildEdit.top + 6,
                                      (rcBuildEdit.right - rcBuildEdit.left) - 12,
                                      (rcBuildEdit.bottom - rcBuildEdit.top) - 12,
                                      h, (HMENU)101, GetModuleHandle(nullptr), nullptr);
        SendMessage(g_editBuild, WM_SETFONT, (WPARAM)fSmallBold, TRUE);
        ShowWindow(g_editBuild, (g_tab == 2) ? SW_SHOW : SW_HIDE);
        return 0;
    }
    case WM_SIZE: {
        int szW = LOWORD(l), szH = HIWORD(l);
        if (szW > 0 && szH > 0) {
            updateLayout(szW, szH);
            InvalidateRect(h, nullptr, FALSE);
        }
        return 0;
    }
    case WM_SETCURSOR: {
        HWND hCursorWnd = (HWND)w;
        if (hCursorWnd == h) {
            POINT pt; GetCursorPos(&pt); ScreenToClient(h, &pt);
            bool hand = false;
            if (inRect(rcBanner, pt.x, pt.y) || inRect(rcHeaderPrev, pt.x, pt.y) ||
                inRect(rcHeaderPreset, pt.x, pt.y) || inRect(rcHeaderNext, pt.x, pt.y)) hand = true;
            for (int i = 0; i < 3 && !hand; i++) if (inRect(rcTabs[i], pt.x, pt.y)) hand = true;
            if (g_tab == 0) {
                if (inRect(rcSaveInTuning, pt.x, pt.y) || inRect(rcReloadInTuning, pt.x, pt.y)) hand = true;
                for (int i = 0; i < kNumSliders && !hand; i++) {
                    RECT t = rcSliderTracks[i];
                    RECT hit{t.left - 10, t.top - 20, t.right + 10, t.bottom + 8};
                    if (inRect(hit, pt.x, pt.y)) hand = true;
                }
            } else if (g_tab == 1) {
                if (inRect(rcSelect, pt.x, pt.y) || inRect(rcPaste, pt.x, pt.y) ||
                    inRect(rcCalib, pt.x, pt.y) || inRect(rcCross, pt.x, pt.y) ||
                    inRect(rcMode, pt.x, pt.y)) hand = true;
            } else if (g_tab == 2) {
                if (inRect(rcNew, pt.x, pt.y) || inRect(rcDel, pt.x, pt.y) ||
                    inRect(rcSave, pt.x, pt.y) || inRect(rcReset, pt.x, pt.y) ||
                    inRect(rcReload, pt.x, pt.y) || inRect(rcHotkey, pt.x, pt.y) ||
                    inRect(rcAds, pt.x, pt.y) || inRect(rcCopyBuild, pt.x, pt.y) ||
                    inRect(rcPasteBuild, pt.x, pt.y)) hand = true;
                if (inRect(rcPresets, pt.x, pt.y)) hand = true;
            }
            if (hand) {
                SetCursor(LoadCursor(nullptr, IDC_HAND));
                return TRUE;
            }
        }
        break;
    }
    case WM_DROPFILES: {
        HDROP hDrop = (HDROP)w;
        wchar_t path[MAX_PATH] = L"";
        if (DragQueryFileW(hDrop, 0, path, MAX_PATH)) {
            Image img;
            if (loadImageFile(path, img)) {
                g_srcImage = img;
                g_hasSrc = true;
                std::wstring wn = path;
                wn = wn.substr(wn.find_last_of(L"\\/") + 1);
                char nb[MAX_PATH];
                WideCharToMultiByte(CP_ACP, 0, wn.c_str(), -1, nb, MAX_PATH, nullptr, nullptr);
                g_srcName = nb;
                g_tab = 1; // switch to vision tab on screenshot drop
                ShowWindow(g_editBuild, SW_HIDE);
                runCalibration();
            } else {
                MessageBoxA(h, "Could not open dropped file as an image.", "Calibration", MB_ICONERROR);
            }
        }
        DragFinish(hDrop);
        return 0;
    }
    case WM_CTLCOLOREDIT:
        SetBkColor((HDC)w, cCardInner);
        SetTextColor((HDC)w, cTextPrimary);
        return (LRESULT)g_brEdit;
    case WM_COMMAND:
        if (LOWORD(w) == 101 && HIWORD(w) == EN_CHANGE && !g_settingText) {
            char b[512]; GetWindowTextA(g_editBuild, b, sizeof b);
            g_presets[g_sel].buildCode = b; syncEngine();
        }
        return 0;
    case WM_TIMER: case WM_APP + 1: {
        InvalidateRect(h, nullptr, FALSE);
        return 0;
    }
    case WM_ERASEBKGND: return 1;
    case WM_PAINT: {
        PAINTSTRUCT ps; HDC dc = BeginPaint(h, &ps);
        RECT cr; GetClientRect(h, &cr);
        HDC mem = CreateCompatibleDC(dc); HBITMAP bm = CreateCompatibleBitmap(dc, cr.right, cr.bottom);
        HGDIOBJ old = SelectObject(mem, bm);
        paint(mem, cr);
        BitBlt(dc, 0, 0, cr.right, cr.bottom, mem, 0, 0, SRCCOPY);
        SelectObject(mem, old); DeleteObject(bm); DeleteDC(mem);
        EndPaint(h, &ps); return 0;
    }
    case WM_RBUTTONDOWN: {
        int x = (short)LOWORD(l), y = (short)HIWORD(l);
        if (g_tab == 2 && inRect(rcHotkey, x, y)) {
            Preset& p = g_presets[g_sel];
            p.hotkey = kHotkeys[(hotkeyIndex(p.hotkey) + kNumHotkeys - 1) % kNumHotkeys].vk;
            syncEngine(); g_status = std::string("Hotkey set to [") + hotkeyName(p.hotkey) + "]";
            InvalidateRect(h, nullptr, FALSE);
        } else if (inRect(rcHeaderPreset, x, y) || inRect(rcHeaderPrev, x, y)) {
            if (!g_presets.empty()) {
                selectPreset((g_sel + (int)g_presets.size() - 1) % (int)g_presets.size());
                savePresets();
            }
            InvalidateRect(h, nullptr, FALSE);
        }
        return 0;
    }
    case WM_LBUTTONDOWN: {
        int x = (short)LOWORD(l), y = (short)HIWORD(l);
        SetFocus(h);

        // Commit preset naming on click outside presets
        if (g_naming && !inRect(rcPresets, x, y)) {
            g_naming = false;
            g_presets[g_sel].name = uniqueName(g_presets[g_sel].name, g_sel);
            savePresets();
        }

        // Header controls (always active)
        if (inRect(rcBanner, x, y)) {
            g_enabled = !g_enabled;
            InvalidateRect(h, nullptr, FALSE);
            return 0;
        }
        if (inRect(rcHeaderPrev, x, y)) {
            if (!g_presets.empty()) {
                selectPreset((g_sel + (int)g_presets.size() - 1) % (int)g_presets.size());
                savePresets();
            }
            InvalidateRect(h, nullptr, FALSE);
            return 0;
        }
        if (inRect(rcHeaderNext, x, y)) {
            if (!g_presets.empty()) {
                selectPreset((g_sel + 1) % (int)g_presets.size());
                savePresets();
            }
            InvalidateRect(h, nullptr, FALSE);
            return 0;
        }
        if (inRect(rcHeaderPreset, x, y)) {
            g_tab = 2;
            ShowWindow(g_editBuild, SW_SHOW);
            InvalidateRect(h, nullptr, FALSE);
            return 0;
        }

        // Tab selection
        for (int i = 0; i < 3; i++) {
            if (inRect(rcTabs[i], x, y)) {
                g_tab = i;
                if (g_tab == 2) {
                    ShowWindow(g_editBuild, SW_SHOW);
                } else {
                    ShowWindow(g_editBuild, SW_HIDE);
                }
                InvalidateRect(h, nullptr, FALSE);
                return 0;
            }
        }

        // Tab 0: Recoil Tuning
        if (g_tab == 0) {
            for (int i = 0; i < kNumSliders; i++) {
                RECT t = rcSliderTracks[i];
                RECT hit{t.left - 10, t.top - 20, t.right + 10, t.bottom + 8};
                if (inRect(hit, x, y)) {
                    g_dragSlider = i; SetCapture(h); setSlider(i, x); InvalidateRect(h, nullptr, FALSE); return 0;
                }
            }
            if (inRect(rcSaveInTuning, x, y)) {
                savePresets();
                g_status = "Saved preset '" + g_presets[g_sel].name + "'";
                InvalidateRect(h, nullptr, FALSE);
                return 0;
            }
            if (inRect(rcReloadInTuning, x, y)) {
                reloadAll();
                InvalidateRect(h, nullptr, FALSE);
                return 0;
            }
        }
        // Tab 1: Pattern & Vision
        else if (g_tab == 1) {
            if (inRect(rcSelect, x, y)) selectScreenshot();
            else if (inRect(rcPaste, x, y)) pasteScreenshot();
            else if (inRect(rcCalib, x, y)) {
                if (g_hasSrc) runCalibration();
                else selectScreenshot();
            } else if (inRect(rcCross, x, y)) {
                if (g_hasExtract) openCalibWin();
                else if (g_hasSrc) runCalibration();
                else selectScreenshot();
            } else if (inRect(rcMode, x, y)) {
                Preset& p = g_presets[g_sel];
                p.patternMode = (p.patternMode == 1 ? 0 : 1);
                syncEngine(); savePresets();
                g_status = (p.patternMode == 1 ? "Classic mode: exact Yonah pattern deltas."
                                               : "Smooth mode: noise-filtered deltas + 12-shot rolling tail.");
            }
        }
        // Tab 2: Presets & Config
        else if (g_tab == 2) {
            if (g_naming && !inRect(rcPresets, x, y)) {
                g_naming = false;
                g_presets[g_sel].name = uniqueName(g_presets[g_sel].name, g_sel);
                savePresets();
            }
            if (inRect(rcPresets, x, y)) {
                int idx = (y - rcPresets.top) / PRESET_H + g_presetScroll;
                if (idx < (int)g_presets.size()) {
                    if (g_naming && idx != g_sel) {
                        g_naming = false;
                        g_presets[g_sel].name = uniqueName(g_presets[g_sel].name, g_sel);
                    }
                    selectPreset(idx);
                    savePresets();
                }
            } else if (inRect(rcNew, x, y)) {
                Preset p = g_presets[g_sel]; p.name = "";
                g_presets.push_back(p); g_sel = (int)g_presets.size() - 1; g_naming = true;
                g_presetScroll = max(0, g_sel - (PRESET_ROWS - 1));
                syncEngine(); refreshBuildEdit();
                g_status = "New preset: type name, then press Enter.";
            } else if (inRect(rcDel, x, y)) {
                if (g_presets.size() <= 1) {
                    MessageBoxA(h, "Cannot delete the only remaining preset.", "Warning", MB_ICONWARNING);
                } else {
                    std::string q = "Delete preset '" + g_presets[g_sel].name + "'?";
                    if (MessageBoxA(h, q.c_str(), "Delete Preset", MB_YESNO | MB_ICONQUESTION) == IDYES) {
                        std::string nm = g_presets[g_sel].name;
                        g_presets.erase(g_presets.begin() + g_sel);
                        selectPreset(max(0, g_sel - 1)); savePresets();
                        g_presetScroll = std::clamp(g_presetScroll, 0, max(0, (int)g_presets.size() - PRESET_ROWS));
                        g_status = "Deleted preset '" + nm + "'";
                    }
                }
            } else if (inRect(rcSave, x, y)) {
                savePresets();
                g_status = "Saved preset '" + g_presets[g_sel].name + "'";
            } else if (inRect(rcHotkey, x, y)) {
                Preset& p = g_presets[g_sel];
                p.hotkey = kHotkeys[(hotkeyIndex(p.hotkey) + 1) % kNumHotkeys].vk;
                syncEngine(); savePresets();
                g_status = std::string("Hotkey set to [") + hotkeyName(p.hotkey) + "]  (left-click = next, right-click = prev)";
            } else if (inRect(rcAds, x, y)) {
                g_presets[g_sel].requireAds ^= true;
                syncEngine(); savePresets();
            } else if (inRect(rcReset, x, y)) {
                resetDefaults();
            } else if (inRect(rcReload, x, y)) {
                reloadAll();
            } else if (inRect(rcCopyBuild, x, y)) {
                const std::string& c = g_presets[g_sel].buildCode;
                if (c.empty()) g_status = "No build code to copy";
                else if (OpenClipboard(h)) {
                    EmptyClipboard(); HGLOBAL g = GlobalAlloc(GMEM_MOVEABLE, c.size() + 1);
                    memcpy(GlobalLock(g), c.c_str(), c.size() + 1); GlobalUnlock(g);
                    SetClipboardData(CF_TEXT, g); CloseClipboard(); g_status = "Build code copied to clipboard";
                }
            } else if (inRect(rcPasteBuild, x, y)) {
                if (OpenClipboard(h)) {
                    HANDLE t = GetClipboardData(CF_TEXT);
                    if (t) {
                        const char* s = (const char*)GlobalLock(t);
                        if (s) {
                            g_presets[g_sel].buildCode = s;
                            refreshBuildEdit();
                            savePresets();
                            g_status = "Build code pasted.";
                        }
                        GlobalUnlock(t);
                    }
                    CloseClipboard();
                }
            }
        }

        InvalidateRect(h, nullptr, FALSE);
        return 0;
    }
    case WM_LBUTTONDBLCLK: {
        int x = (short)LOWORD(l), y = (short)HIWORD(l);
        if (g_tab == 2 && inRect(rcPresets, x, y)) {
            int idx = (y - rcPresets.top) / PRESET_H + g_presetScroll;
            if (idx < (int)g_presets.size()) {
                selectPreset(idx);
                g_naming = true;
                g_status = "Renaming preset '" + g_presets[g_sel].name + "': type new name and press Enter.";
                InvalidateRect(h, nullptr, FALSE);
            }
        }
        return 0;
    }
    case WM_MOUSEMOVE:
        if (g_dragSlider >= 0) { setSlider(g_dragSlider, (short)LOWORD(l)); InvalidateRect(h, nullptr, FALSE); }
        return 0;
    case WM_LBUTTONUP:
        if (g_dragSlider >= 0) {
            g_dragSlider = -1;
            ReleaseCapture();
            savePresets();
        }
        return 0;
    case WM_MOUSEWHEEL: {
        POINT pt{(short)LOWORD(l), (short)HIWORD(l)}; ScreenToClient(h, &pt);
        int dir = GET_WHEEL_DELTA_WPARAM(w) > 0 ? 1 : -1;
        if (g_tab == 0) {
            for (int i = 0; i < kNumSliders; i++) {
                RECT t = sliderTrack(i);
                RECT hit{t.left - 10, t.top - 22, t.right + 10, t.bottom + 10};
                if (inRect(hit, pt.x, pt.y)) {
                    const SliderDef& d = kSliders[i];
                    double v = std::clamp(sliderValue(i) + dir * d.step, d.lo, d.hi);
                    g_presets[g_sel].*d.field = std::round(v / d.step) * d.step;
                    syncEngine();
                    savePresets();
                    InvalidateRect(h, nullptr, FALSE);
                    return 0;
                }
            }
        }
        if (g_tab == 2 && inRect(rcPresets, pt.x, pt.y)) {
            g_presetScroll = std::clamp(g_presetScroll - dir, 0, max(0, (int)g_presets.size() - PRESET_ROWS));
            InvalidateRect(h, nullptr, FALSE);
            return 0;
        }
        return 0;
    }
    case WM_KEYDOWN:
        if (!g_naming) {
            if (w == '1') {
                g_tab = 0; ShowWindow(g_editBuild, SW_HIDE); InvalidateRect(h, nullptr, FALSE); return 0;
            }
            if (w == '2') {
                g_tab = 1; ShowWindow(g_editBuild, SW_HIDE); InvalidateRect(h, nullptr, FALSE); return 0;
            }
            if (w == '3') {
                g_tab = 2; ShowWindow(g_editBuild, SW_SHOW); InvalidateRect(h, nullptr, FALSE); return 0;
            }
        }
        if (w == VK_F2 && !g_naming) {
            g_tab = 2; ShowWindow(g_editBuild, SW_SHOW);
            g_naming = true;
            g_status = "Renaming preset '" + g_presets[g_sel].name + "': type new name and press Enter.";
            InvalidateRect(h, nullptr, FALSE);
            return 0;
        }
        if (w == 'V' && (GetKeyState(VK_CONTROL) & 0x8000)) {
            if (g_naming) {
                g_naming = false;
                g_presets[g_sel].name = uniqueName(g_presets[g_sel].name, g_sel);
                savePresets();
            }
            pasteScreenshot();
            InvalidateRect(h, nullptr, FALSE);
            return 0;
        }
        InvalidateRect(h, nullptr, FALSE);
        return 0;
    case WM_CHAR:
        if (g_naming) {
            std::string& n = g_presets[g_sel].name;
            if (w == VK_RETURN || w == VK_ESCAPE) {
                g_naming = false;
                n = uniqueName(n, g_sel);
                savePresets(); g_status = "Created preset '" + n + "'";
            } else if (w == VK_BACK) { if (!n.empty()) n.pop_back(); }
            else if (w >= 32 && w < 127 && n.size() < 22 && w != '[' && w != ']') n.push_back((char)w);
            InvalidateRect(h, nullptr, FALSE);
        }
        return 0;
    case WM_CLOSE:
        if (g_naming) { g_naming = false; g_presets[g_sel].name = uniqueName(g_presets[g_sel].name, g_sel); }
        savePresets();
        DestroyWindow(h);
        return 0;
    case WM_DESTROY: g_running = false; PostQuitMessage(0); return 0;
    }
    return DefWindowProcW(h, m, w, l);
}

int WINAPI WinMain(HINSTANCE hi, HINSTANCE, LPSTR cmd, int) {
    SetProcessDPIAware();
    ULONG_PTR gdipTok; Gdiplus::GdiplusStartupInput gi; Gdiplus::GdiplusStartup(&gdipTok, &gi, nullptr);
    g_iniPath = exeDir() + "presets.ini";

    InitializeCriticalSection(&g_cs);
    timeBeginPeriod(1);
    loadPresets();
    syncEngine();

    // Headless / Terminal check: DFRecoil.exe --test [image.png]
    if (cmd && strstr(cmd, "--test")) {
        HANDLE hOut = GetStdHandle(STD_OUTPUT_HANDLE);
        if (!hOut || hOut == INVALID_HANDLE_VALUE) {
            if (AttachConsole(ATTACH_PARENT_PROCESS)) {
                hOut = GetStdHandle(STD_OUTPUT_HANDLE);
                freopen("CONOUT$", "w", stdout);
                freopen("CONOUT$", "w", stderr);
            }
        }
        std::string c = cmd, path = c.substr(c.find("--test") + 6);
        while (!path.empty() && (path.front() == ' ' || path.front() == '"')) path.erase(path.begin());
        while (!path.empty() && (path.back() == ' ' || path.back() == '"')) path.pop_back();

        std::ostringstream out;

        auto testSingleImage = [&](const std::wstring& wp, const std::string& name) -> bool {
            Image img;
            if (!loadImageFile(wp.c_str(), img)) {
                out << "[" << name << "] ERR open\n";
                printf("[%s] ERR open\n", name.c_str());
                return false;
            }
            Extract ex = extractDots(img);
            Preset p; p.green = ex.green; p.grey = ex.grey;
            compressionRatios(p.grey, p.green, p.vRatio, p.hRatio);
            KickParams kp = kickParams(p.green.size() >= 2 ? p.green : p.grey);
            p.calKick = kp.kick; p.calKickShots = kp.shots;
            Pattern cl = classicPattern(p), sm = smoothPattern(p);
            int pct = matchPercent(ex.grey.size(), ex.green.size());

            out << "=== " << name << " ===\n";
            out << "green=" << ex.green.size() << " grey=" << ex.grey.size() << " sync=" << pct << "%\n";
            out << "V " << kp.vScale << " H " << kp.hScale << " kick " << kp.kick << " " << kp.shots
                << " ratio " << p.vRatio << " " << p.hRatio << "\n";
            out << "classic tail " << cl.tail.dx << " " << cl.tail.dy << " n " << cl.shots.size()
                << " | smooth tail " << sm.tail.dx << " " << sm.tail.dy << " n " << sm.shots.size() << "\n";
            out << "green:"; for (auto& d : ex.green) out << " " << d.x << "," << d.y; out << "\n";
            out << "grey:"; for (auto& d : ex.grey) out << " " << d.x << "," << d.y; out << "\n";

            char buf[512];
            snprintf(buf, sizeof buf, "[%s] green=%d grey=%d V=%.2f H=%.2f kick=%.2f(%d) ratio=%.2f/%.2f sync=%d%%\n",
                     name.c_str(), (int)ex.green.size(), (int)ex.grey.size(), kp.vScale, kp.hScale,
                     kp.kick, kp.shots, p.vRatio, p.hRatio, pct);
            if (hOut && hOut != INVALID_HANDLE_VALUE) {
                DWORD written = 0;
                WriteFile(hOut, buf, (DWORD)strlen(buf), &written, nullptr);
            } else {
                printf("%s", buf); fflush(stdout);
            }

            bool ok = ex.green.size() >= 20 && ex.grey.size() >= 13 && p.vRatio >= 0.2 && p.vRatio <= 1.2 && p.hRatio >= 0.1 && p.hRatio <= 1.5;
            return ok;
        };

        if (!path.empty() && path != "all" && path != "--all") {
            std::wstring wp(path.begin(), path.end());
            std::string nm = path.substr(path.find_last_of("\\/") + 1);
            testSingleImage(wp, nm);
        } else {
            wchar_t sdir[MAX_PATH];
            ExpandEnvironmentStringsW(L"%USERPROFILE%\\Pictures\\Screenshots", sdir, MAX_PATH);
            std::wstring searchPattern = std::wstring(sdir) + L"\\DeltaForceClient-Win64-Shipping_*.png";
            WIN32_FIND_DATAW fd;
            HANDLE hFind = FindFirstFileW(searchPattern.c_str(), &fd);
            int passed = 0, total = 0;
            if (hFind != INVALID_HANDLE_VALUE) {
                do {
                    std::wstring fullPath = std::wstring(sdir) + L"\\" + fd.cFileName;
                    char nb[MAX_PATH];
                    WideCharToMultiByte(CP_ACP, 0, fd.cFileName, -1, nb, MAX_PATH, nullptr, nullptr);
                    total++;
                    if (testSingleImage(fullPath, nb)) passed++;
                } while (FindNextFileW(hFind, &fd));
                FindClose(hFind);
            }
            char sbuf[128];
            snprintf(sbuf, sizeof sbuf, "Total tests: %d / %d PASSED\n", passed, total);
            if (hOut && hOut != INVALID_HANDLE_VALUE) {
                DWORD written = 0;
                WriteFile(hOut, sbuf, (DWORD)strlen(sbuf), &written, nullptr);
            } else {
                printf("%s", sbuf); fflush(stdout);
            }
            out << "Summary: " << passed << " / " << total << " passed\n";
        }

        std::ofstream(exeDir() + "test_out.txt") << out.str();
        timeEndPeriod(1);
        Gdiplus::GdiplusShutdown(gdipTok);
        return 0;
    }

    fTitle = CreateFontA(24, 0, 0, 0, FW_BOLD, 0, 0, 0, DEFAULT_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, "Segoe UI");
    fSection = CreateFontA(19, 0, 0, 0, FW_BOLD, 0, 0, 0, DEFAULT_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, "Segoe UI");
    fLabel = CreateFontA(15, 0, 0, 0, FW_SEMIBOLD, 0, 0, 0, DEFAULT_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, "Segoe UI");
    fBig = CreateFontA(19, 0, 0, 0, FW_BOLD, 0, 0, 0, DEFAULT_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, "Segoe UI");
    fSmall = CreateFontA(13, 0, 0, 0, FW_NORMAL, 0, 0, 0, DEFAULT_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, "Segoe UI");
    fSmallBold = CreateFontA(13, 0, 0, 0, FW_BOLD, 0, 0, 0, DEFAULT_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, "Segoe UI");
    fBtn = CreateFontA(14, 0, 0, 0, FW_SEMIBOLD, 0, 0, 0, DEFAULT_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, "Segoe UI");
    fTab = CreateFontA(14, 0, 0, 0, FW_SEMIBOLD, 0, 0, 0, DEFAULT_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, "Segoe UI");
    g_brEdit = CreateSolidBrush(cCardInner);

    WNDCLASSW wc{}; wc.lpfnWndProc = wndProc; wc.hInstance = hi; wc.lpszClassName = L"DFRecoilWnd";
    wc.hCursor = LoadCursor(nullptr, IDC_ARROW); wc.hIcon = LoadIcon(nullptr, IDI_APPLICATION); RegisterClassW(&wc);
    WNDCLASSW cc{}; cc.lpfnWndProc = calibProc; cc.hInstance = hi; cc.lpszClassName = L"DFCalibWnd";
    cc.hCursor = LoadCursor(nullptr, IDC_CROSS); RegisterClassW(&cc);

    RECT workArea{};
    SystemParametersInfoW(SPI_GETWORKAREA, 0, &workArea, 0);
    int workW = (workArea.right > workArea.left) ? (workArea.right - workArea.left) : 1920;
    int workH = (workArea.bottom > workArea.top) ? (workArea.bottom - workArea.top) : 1080;

    int clientW = 1080;
    int clientH = 620;
    if (workH < 700) clientH = max(560, workH - 65);
    if (workW < 1120) clientW = max(940, workW - 30);

    DWORD st = WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX | WS_CLIPCHILDREN;
    RECT r{0, 0, clientW, clientH};
    AdjustWindowRect(&r, st, FALSE);
    int winW = r.right - r.left;
    int winH = r.bottom - r.top;

    int posX = workArea.left + max(0, (workW - winW) / 2);
    int posY = workArea.top + max(0, (workH - winH) / 2);

    updateLayout(clientW, clientH);

    g_hwnd = CreateWindowW(L"DFRecoilWnd", L"Delta Force Recoil Manager", st,
                           posX, posY, winW, winH, nullptr, nullptr, hi, nullptr);
    refreshBuildEdit();
    ShowWindow(g_hwnd, SW_SHOW);
    HANDLE th = CreateThread(nullptr, 0, workerThread, nullptr, 0, nullptr);
    SetThreadPriority(th, THREAD_PRIORITY_ABOVE_NORMAL);
    MSG msg;
    while (GetMessage(&msg, nullptr, 0, 0)) { TranslateMessage(&msg); DispatchMessage(&msg); }
    g_running = false; WaitForSingleObject(th, 1000);
    timeEndPeriod(1);
    Gdiplus::GdiplusShutdown(gdipTok);
    return 0;
}
