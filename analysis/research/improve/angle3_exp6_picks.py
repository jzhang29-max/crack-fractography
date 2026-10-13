import sys, json, ast
sys.path.insert(0, "/Users/jiamingzhang/Desktop/APP/crack-fractography/analysis/research/improve")
import angle3_candidates as A
import tilebench as TB
grid = {ast.literal_eval(k): v for k, v in json.load(open(A.WORK + "/grid.json")).items()}
r = TB.evaluate("x", grid, criterion="iou", quiet=True)
print(f"{'specimen held out':<22} {'variant the other 12 specimens picked':<34} held-out IoU")
for sp in sorted(r["picks"]):
    print(f"  {sp:<20} {r['picks'][sp]:<34} {r['per_specimen'][sp]['iou']:.4f}  "
          f"P {r['per_specimen'][sp]['precision']:.4f} R {r['per_specimen'][sp]['recall']:.4f}")
