import os, sys, glob, subprocess
sys.path.insert(0, r"C:\Users\Yonah\Downloads\Machine Archives\Delta Force - Yonah\core")
import extractor

files = glob.glob(r"C:\Users\Yonah\Pictures\Screenshots\DeltaForceClient-Win64-Shipping_*.png")
print(f"Testing {len(files)} screenshot files:")

for f in sorted(files):
    name = os.path.basename(f)
    py_res = extractor.calibrate_from_image(f)
    py_str = f"green={py_res['green_count']} grey={py_res['grey_count']} V={py_res['vertical_scale']:.2f} H={py_res['horizontal_scale']:.2f} kick={py_res['initial_kick_mult']:.2f}({py_res['kick_decay_shots']}) ratio={py_res['vert_mult']:.2f}/{py_res['horiz_mult']:.2f} sync={py_res['match_percent']}%"
    proc = subprocess.run([r"C:\Users\Yonah\Downloads\Machine Archives\Delta Force - Trial\DFRecoil.exe", "--test", f], capture_output=True, text=True)
    cpp_out = proc.stdout.strip()
    match = py_str in cpp_out
    print(f"[{name}] {'MATCH' if match else 'DIFF'}")
    if not match:
        print(f"  PY : {py_str}")
        print(f"  CPP: {cpp_out}")
