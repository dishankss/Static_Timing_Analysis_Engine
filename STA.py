import argparse
from pathlib import Path
from collections import deque 

# AI usage note:
# We used ChatGPT mostly during Phase 2 and for some bugs in Phase 1.
# About 40-50% of the final code was based on AI suggestions.

class Node:
    # Simple node object for the circuit graph.
    # name is the wire name.
    # gate_type is set for gate output nodes.
    def __init__(self, name, gate_type=None):
        self.name = name
        self.gate_type = gate_type
        self.fanin = []
        self.fanout = []  

# Phase 1: .bench parser
# This reads the circuit netlist and builds a graph.
# Complexity is O(V + E).
def parse_circuit(file_path: Path):
    nodes, pis, pos, gate_order = {}, [], [], []

    # Helper to create nodes only once.
    def get_node(n):
        if n not in nodes:
            nodes[n] = Node(n)
        return nodes[n]

    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments.
            if not line or line.startswith("#"):
                continue

            # Parse INPUT lines.
            if line.startswith("INPUT"):
                n = line[line.find("(") + 1:line.find(")")]
                pis.append(n)
                get_node(n)

            # Parse OUTPUT lines.
            # We store OUTPUT markers in fanout using "OUTPUT_<po>".
            elif line.startswith("OUTPUT"):
                n = line[line.find("(") + 1:line.find(")")]
                pos.append(n)
                get_node(n).fanout.append("OUTPUT_" + n)

            # Parse gate lines.
            # Format: out = GATE(in1, in2, ...)
            else:
                left, right = line.split("=")
                out = left.strip()
                gtype = right[:right.find("(")].strip()
                ins = right[right.find("(") + 1:right.find(")")]
                fanins = [x.strip() for x in ins.split(",") if x.strip()]

                out_node = get_node(out)
                out_node.gate_type = gtype.upper()
                gate_order.append(out)

                # Connect fanin to out edges.
                for fi in fanins:
                    get_node(fi).fanout.append(out)
                    out_node.fanin.append(fi)

    return nodes, pis, pos, gate_order

# Phase 1: NLDM parser 
# AI assisted with the initial structure.
# We later fixed a real bug in reading "values()" rows.
# Bug: Some LUT rows were missed.
# Fix: Keep reading until we see the line that contains ");".
def parse_nldm(file_path: Path, dump_delays=False, dump_slews=False):
    cells = {}
    cur_cell = None
    cur_block = None
    reading_values = False
    temp_values = []

    # Create a cell entry if not present.
    def ensure_cell(c):
        if c not in cells:
            cells[c] = {
                "capacitance": 0.0,
                "delay": {"slew_index": [], "load_index": [], "values": []},
                "slew":  {"slew_index": [], "load_index": [], "values": []},
            }

    with open(file_path, "r") as f:
        for line in f:
            s = line.strip()

            # Start of a liberty cell.
            if s.startswith("cell ("):
                cur_cell = s.split("(")[1].split(")")[0].strip()
                ensure_cell(cur_cell)
                cur_block = None
                reading_values = False
                temp_values = []
                continue

            # Ignore everything until a cell is found.
            if cur_cell is None:
                continue

            # Read input capacitance for each cell.
            if s.startswith("capacitance"):
                parts = s.replace(";", "").split(":")
                if len(parts) == 2:
                    try:
                        cells[cur_cell]["capacitance"] = float(parts[1].strip())
                    except ValueError:
                        cells[cur_cell]["capacitance"] = 0.0
                continue

            # Enter delay LUT block.
            if s.startswith("cell_delay"):
                cur_block = "delay"
                continue

            # Enter slew LUT block.
            if s.startswith("output_slew"):
                cur_block = "slew"
                continue

            # Parse index_1 (input slew axis).
            if cur_block and ("index_1" in s) and ('"' in s):
                cells[cur_cell][cur_block]["slew_index"] = [v.strip() for v in s.split('"')[1].split(",")]
                continue

            # Parse index_2 (load capacitance axis).
            if cur_block and ("index_2" in s) and ('"' in s):
                cells[cur_cell][cur_block]["load_index"] = [v.strip() for v in s.split('"')[1].split(",")]
                continue

            # Start reading LUT values rows.
            if cur_block and ("values (" in s):
                reading_values = True
                temp_values = []
                if '"' in s:
                    temp_values.append(s.split('"')[1])
                continue

            # Continue reading LUT values rows.
            # This must continue until the line containing ");".
            # This fix prevents missing LUT matrix rows.
            if reading_values:
                if '"' in s:
                    temp_values.append(s.split('"')[1])
                if ");" in s:
                    reading_values = False
                    cells[cur_cell][cur_block]["values"] = temp_values
                continue

            # End of a liberty block.
            if s == "}":
                cur_block = None
                reading_values = False
                temp_values = []

    # output dumps for Phase 1.
    if dump_delays:
        dump_lut_file(cells, "delay", "delay_LUT.txt", "delays")
    if dump_slews:
        dump_lut_file(cells, "slew", "slew_LUT.txt", "slews")

    return cells

# Writes parsed LUT tables to a text file.
def dump_lut_file(cells, which, outname, label):
    with open(outname, "w") as out:
        for cell, data in cells.items():
            lut = data[which]
            out.write(f"cell: {cell}\n")
            out.write("input slews: " + ",".join(lut["slew_index"]) + "\n")
            out.write("load cap: " + ",".join(lut["load_index"]) + "\n")
            out.write(label + ":\n")
            for row in lut["values"]:
                out.write(row + "\n")
            out.write("\n")
    print(f"{which.upper()} LUT written to {outname}")

# Writes circuit stats and connectivity to a file.
def write_circuit_details(nodes, pis, pos, gate_order, out_file="ckt_details.txt"):
    gate_count = {}
    # Count how many gates of each type exist.
    for g in gate_order:
        gt = nodes[g].gate_type
        gate_count[gt] = gate_count.get(gt, 0) + 1

    with open(out_file, "w") as out:
        out.write(f"{len(pis)} primary inputs\n")
        out.write(f"{len(pos)} primary outputs\n")
        for gt, cnt in gate_count.items():
            out.write(f"{cnt} {gt} gates\n")

        out.write("\nFanout...\n")
        # Write fanout list for each gate output.
        for g in gate_order:
            node = nodes[g]
            label = f"{node.gate_type}-{node.name}"
            fanouts = []
            for fo in node.fanout:
                if fo.startswith("OUTPUT_"):
                    fanouts.append("OUTPUT-" + fo.split("_", 1)[1])
                else:
                    fanouts.append(f"{nodes[fo].gate_type}-{fo}")
            out.write(label + ": " + ", ".join(fanouts) + "\n")

        out.write("\nFanin...\n")
        pi_set = set(pis)
        # Write fanin list for each gate output.
        for g in gate_order:
            node = nodes[g]
            label = f"{node.gate_type}-{node.name}"
            fanins = []
            for fi in node.fanin:
                fanins.append(("INPUT-" + fi) if fi in pi_set else f"{nodes[fi].gate_type}-{fi}")
            out.write(label + ": " + ", ".join(fanins) + "\n")

    print(f"Circuit details written to {out_file}")

# Phase 2: STA
# AI helped mainly in Phase 2 STA structure and math.
# We later verified and corrected logic issues.
PI_ARRIVAL = 0.0
PI_SLEW = 0.002  # ns

# Pre-parse all LUT float tables once from the raw string data.
# This avoids re-parsing strings on every gate during forward traversal.
# Called once after parse_nldm; result passed into forward_traversal.
def preparse_lut_tables(cells):
    lut_cache = {}
    for cell_name, cell_data in cells.items():
        lut_cache[cell_name] = {}
        for lut_type in ("delay", "slew"):
            lut = cell_data[lut_type]
            si = [float(v) for v in lut["slew_index"]]
            li = [float(v) for v in lut["load_index"]]
            mx = []
            for row_str in lut["values"]:
                row_str = row_str.rstrip(";").strip()
                row = [float(v.strip()) for v in row_str.split(",") if v.strip()]
                if row:
                    mx.append(row)
            lut_cache[cell_name][lut_type] = (si, li, mx)
    return lut_cache

# use in-degree dict built from fanin traversal
def topological_sort(nodes, pis, gate_order):
    pi_set = set(pis)
    in_degree = {g: 0 for g in gate_order}

    # Build adjacency and compute in-degrees from fanin lists.
    for g in gate_order:
        for fi in nodes[g].fanin:
            if fi not in pi_set and fi in in_degree:
                in_degree[fi]  # ensure key exists
                in_degree[g] += 0  # already counted below

    # Recompute cleanly: count how many fanins are gates (not PIs).
    in_degree = {g: 0 for g in gate_order}
    for g in gate_order:
        for fi in nodes[g].fanin:
            if fi not in pi_set:
                in_degree[g] += 1

    # Use deque for efficient BFS (O(1) popleft vs O(n) list pop).
    q = deque([g for g in gate_order if in_degree[g] == 0])
    topo = []

    while q:
        cur = q.popleft()  #  deque popleft is O(1) vs list head pointer
        topo.append(cur)
        for fo in nodes[cur].fanout:
            if fo.startswith("OUTPUT_"):
                continue
            if fo in in_degree:
                in_degree[fo] -= 1
                if in_degree[fo] == 0:
                    q.append(fo)

    return topo

# Retrieve pre-parsed LUT float arrays from the cache.
# The actual parsing is done once in preparse_lut_tables before traversal.
def parse_lut_values(lut_cache, cell_name, lut_type):
    return lut_cache[cell_name][lut_type]

# AI helped with this math structure.
# Input is (tau, cap).
# Output is interpolated delay or slew.
def lut_interpolate(si, li, mx, tau, cap):
    # Find bracket indices for interpolation.
    # If outside range, clamp to edge.
    def bracket(arr, x):
        if x <= arr[0]:
            return 0, 0
        if x >= arr[-1]:
            return len(arr) - 1, len(arr) - 1
        for i in range(len(arr) - 1):
            if arr[i] <= x < arr[i + 1]:
                return i, i + 1
        return len(arr) - 1, len(arr) - 1

    r1, r2 = bracket(si, tau)
    c1, c2 = bracket(li, cap)

    # Exact grid point.
    if r1 == r2 and c1 == c2:
        return mx[r1][c1]

    # Interpolate only in load direction.
    if r1 == r2:
        dC = li[c2] - li[c1]
        return mx[r1][c1] if dC == 0 else mx[r1][c1] + ((cap - li[c1]) / dC) * (mx[r1][c2] - mx[r1][c1])

    # Interpolate only in slew direction.
    if c1 == c2:
        dT = si[r2] - si[r1]
        return mx[r1][c1] if dT == 0 else mx[r1][c1] + ((tau - si[r1]) / dT) * (mx[r2][c1] - mx[r1][c1])

    # Full bilinear interpolation case.
    tau1, tau2 = si[r1], si[r2]
    cap1, cap2 = li[c1], li[c2]
    v11, v12 = mx[r1][c1], mx[r1][c2]
    v21, v22 = mx[r2][c1], mx[r2][c2]
    denom = (cap2 - cap1) * (tau2 - tau1)
    if denom == 0:
        return v11

    return (
        v11 * (cap2 - cap) * (tau2 - tau) +
        v12 * (cap - cap1) * (tau2 - tau) +
        v21 * (cap2 - cap) * (tau - tau1) +
        v22 * (cap - cap1) * (tau - tau1)
    ) / denom

# Using an explicit prefix map
def resolve_cell_name(gate_type, cells):
    if gate_type is None:
        return next(iter(cells))
    up = gate_type.upper()
    if up.startswith("NAND"):
        candidate = "NAND2_X1"
    elif up.startswith("NOR"):
        candidate = "NOR2_X1"
    elif up.startswith("AND"):
        candidate = "AND2_X1"
    elif up.startswith("OR"):
        candidate = "OR2_X1"
    elif up.startswith("XOR"):
        candidate = "XOR2_X1"
    elif up.startswith("BUF"):
        candidate = "BUF_X1"
    elif up.startswith("INV") or up.startswith("NOT"):
        candidate = "INV_X1"
    else:
        candidate = "INV_X1"
    # Fall back to first available cell if candidate not in liberty.
    if candidate in cells:
        return candidate
    return next(iter(cells))

# Return a cell input capacitance from liberty data.
def get_cell_cap(cells, cell_name):
    try:
        return float(cells.get(cell_name, {}).get("capacitance", 0.0))
    except Exception:
        return 0.0

# Get inverter input capacitance.
def get_inv_cap(cells):
    if "INV_X1" in cells:
        return get_cell_cap(cells, "INV_X1")
    for c in cells:
        u = c.upper()
        if ("INV" in u) or ("NOT" in u):
            return get_cell_cap(cells, c)
    return get_cell_cap(cells, next(iter(cells)))

# compute_load_cap: sum up input capacitances of all fanout gates.
# Per project spec: "The input capacitance of the n-input gate may be assumed to remain unchanged from that of the corresponding 1 or 2-input gate."
# Therefore we do NOT scale the fanout gate's capacitance by (n/2).
def compute_load_cap(node, nodes, cells, inv_cap):
    drives_po = False
    cap = 0.0

    for fo in node.fanout:
        if fo.startswith("OUTPUT_"):
            drives_po = True
        else:
            fo_node = nodes[fo]
            fo_cell = resolve_cell_name(fo_node.gate_type, cells)
            # No scaling of capacitance — spec says input cap is unchanged for n-input gates.
            cap += get_cell_cap(cells, fo_cell)

    if drives_po:
        cap += 4.0 * inv_cap
    return cap

# arc_delay_map for the correct backward pass and critical path trace
# forward_traversal: compute arrival times, output slews, and per-arc delays.
#   1. lut_cache (pre-parsed floats) is passed in -- no string->float parsing per gate.
#   2. inv_cap is computed once outside the loop.
#   3. cell name and LUT lookup results are fetched per gate, but from the fast dict cache.
# All these eliminate the dominant per-gate overhead on large circuits.
def forward_traversal(nodes, pis, topo, cells, lut_cache):
    inv_cap = get_inv_cap(cells)  # computed once, not inside the loop
    arrival = {pi: PI_ARRIVAL for pi in pis}
    slew = {pi: PI_SLEW for pi in pis}
    arc_delay_map = {}

    for g in topo:
        node = nodes[g]
        n_in = len(node.fanin)
        # Scaling for >2-input gates per project spec.
        scale = (n_in / 2.0) if n_in > 2 else 1.0

        # Pass pre-computed inv_cap to avoid calling get_inv_cap inside.
        cap_load = compute_load_cap(node, nodes, cells, inv_cap)
        cell = resolve_cell_name(node.gate_type, cells)

        # Use pre-parsed cache: no string parsing here, just dict lookup.
        si_d, li_d, mx_d = parse_lut_values(lut_cache, cell, "delay")
        si_s, li_s, mx_s = parse_lut_values(lut_cache, cell, "slew")

        best_arr = -1e30
        best_fanin = None
        arc_delays = {}

        # Compute per-arc delay and record all of them.
        for fi in node.fanin:
            tau_in = slew.get(fi, PI_SLEW)
            arr_in = arrival.get(fi, PI_ARRIVAL)

            d = lut_interpolate(si_d, li_d, mx_d, tau_in, cap_load) * scale
            arc_delays[fi] = d
            cand = arr_in + d

            if cand > best_arr:
                best_arr = cand
                best_fanin = fi

        arrival[g] = best_arr if best_fanin is not None else 0.0
        arc_delay_map[g] = arc_delays

        # Output slew comes from the worst (max arrival) input path.
        if best_fanin is not None:
            tau_best = slew.get(best_fanin, PI_SLEW)
            best_slew = lut_interpolate(si_s, li_s, mx_s, tau_best, cap_load) * scale
        else:
            best_slew = PI_SLEW
        slew[g] = best_slew

    return arrival, slew, arc_delay_map

def backward_traversal(nodes, pis, pos, topo, arrival, slew, cells, circuit_delay, arc_delay_map):
    rat = 1.1 * circuit_delay
    pi_set = set(pis)
    po_set = set(pos)

    # Initialize required time to infinity for all nodes; POs get rat.
    all_gate_names = set(topo)
    req_time = {n: float('inf') for n in (set(pis) | all_gate_names | po_set)}
    for po in pos:
        req_time[po] = rat

    # Backward pass over gates in reverse topological order.
    for g in reversed(topo):
        # Propagate required time backward through each fanin arc.
        for fi in nodes[g].fanin:
            arc_d = arc_delay_map[g].get(fi, 0.0)
            candidate = req_time[g] - arc_d
            fi_key = fi if fi in req_time else fi
            if fi_key in req_time:
                req_time[fi_key] = min(req_time[fi_key], candidate)

    # Compute slack = required - arrival for every node.
    slack = {}
    for n in req_time:
        slack[n] = req_time[n] - arrival.get(n, 0.0)

    # PO slack is always rat - arrival[po] (per spec).
    for po in pos:
        slack[po] = rat - arrival.get(po, 0.0)

    return req_time, slack

# critical path trace to use max-arrival backward trace
# using arc_delay_map, instead of following min-slack nodes.
def find_critical_path(nodes, pis, pos, arrival, arc_delay_map):
    pi_set = set(pis)

    # Start from PO with highest arrival time (worst slack).
    best_po = max(pos, key=lambda p: arrival.get(p, 0.0))

    # Trace backwards from best_po to a PI.
    # We append each visited gate then reverse, giving PI -> ... -> gate -> OUTPUT.
    path = [best_po]
    current = best_po

    while current not in pi_set:
        if current not in nodes or not nodes[current].fanin:
            break
        # Pick fanin that contributed the latest arrival (arrival[fi] + arc_delay[fi]).
        fanins = nodes[current].fanin
        arc_d = arc_delay_map.get(current, {})
        best_fi = max(
            fanins,
            key=lambda fi: arrival.get(fi, 0.0) + arc_d.get(fi, 0.0)
        )
        current = best_fi
        path.append(current)

    path.reverse()
    # Append the OUTPUT marker — best_po in path prints as NAND-22 (gate label),
    path.append("OUT:" + best_po)
    return path, best_po

# STA results to output file.
def write_sta_results(nodes, pis, pos, gate_order, circuit_delay, slack, crit_path, best_po, out_file="ckt_traversal.txt"):
    pi_set, po_set = set(pis), set(pos)

    with open(out_file, "w") as out:
        out.write(f"Circuit delay: {circuit_delay * 1000:.5f}ps\n")
        out.write("\n")
        out.write("Gate slacks:\n")

        for pi in pis:
            out.write(f"INPUT-{pi}: {slack.get(pi, 0.0) * 1000:.5f} ps\n")
        for po in pos:
            out.write(f"OUTPUT-{po}: {slack.get(po, 0.0) * 1000:.5f} ps\n")
        for g in gate_order:
            out.write(f"{nodes[g].gate_type}-{g}: {slack.get(g, 0.0) * 1000:.5f} ps\n")

        out.write("\nCritical path:\n")
        labels = []
        for n in crit_path:
            if n.startswith("OUT:"):
                # This is the explicit OUTPUT marker appended at path end.
                labels.append("OUTPUT-" + n[4:])
            elif n in pi_set:
                labels.append("INPUT-" + n)
            elif n in nodes and nodes[n].gate_type:
                # Gate nodes (including those that are also POs) print as GATE_TYPE-name.
                # e.g. NAND-22 not OUTPUT-22, so NAND-22 appears before OUTPUT-22 in path.
                labels.append(f"{nodes[n].gate_type}-{n}")
            else:
                labels.append("OUTPUT-" + n)
        out.write(", ".join(labels) + "\n")

    print(f"STA results written to {out_file}")

# Main 
# Uses argparse to support Phase 1 and Phase 2 commands.
def main():
    ap = argparse.ArgumentParser(description="Mini project 1")
    ap.add_argument("--read_ckt", type=str)
    ap.add_argument("--read_nldm", type=str)
    ap.add_argument("--delays", action="store_true")
    ap.add_argument("--slews", action="store_true")
    args = ap.parse_args()

    # Case A: Phase-1 circuit details only
    if args.read_ckt and not args.read_nldm:
        nodes, pis, pos, order = parse_circuit(Path(args.read_ckt))
        write_circuit_details(nodes, pis, pos, order)
        return

    # Case B: Phase-1 LUT dump only
    if args.read_nldm and (args.delays or args.slews) and not args.read_ckt:
        parse_nldm(Path(args.read_nldm), dump_delays=args.delays, dump_slews=args.slews)
        return

    # Case C: Phase-2 run (ALSO generate Phase-1 required outputs)
    if args.read_ckt and args.read_nldm and not args.delays and not args.slews:
        ckt = Path(args.read_ckt)
        lib = Path(args.read_nldm)
        if not ckt.exists():
            print("Error: Circuit file does not exist.")
            return
        if not lib.exists():
            print("Error: Liberty file does not exist.")
            return

        nodes, pis, pos, order = parse_circuit(ckt)

        # Also dumps delay and slew LUT files.
        cells = parse_nldm(lib, dump_delays=True, dump_slews=True)
        if not cells:
            print("Error: Liberty parsed but no cells found.")
            return

        # Phase-1 required output (ckt_details)
        write_circuit_details(nodes, pis, pos, order)

        # Phase-2 STA
        topo = topological_sort(nodes, pis, order)

        # Pre-parse LUT string rows into float arrays once before traversal.
        # Avoids repeated string->float conversion inside the per-gate hot loop.
        lut_cache = preparse_lut_tables(cells)

        arrival, slew, arc_delay_map = forward_traversal(nodes, pis, topo, cells, lut_cache)

        circuit_delay = max((arrival.get(po, 0.0) for po in pos), default=0.0)
        print(f"Circuit delay: {circuit_delay * 1000:.5f}ps")

        # pass arc_delay_map to backward traversal.
        _, slack = backward_traversal(nodes, pis, pos, topo, arrival, slew, cells, circuit_delay, arc_delay_map)

        # find_critical_path uses arrival + arc delays.
        crit, best_po = find_critical_path(nodes, pis, pos, arrival, arc_delay_map)

        write_sta_results(nodes, pis, pos, order, circuit_delay, slack, crit, best_po)
        return

if __name__ == "__main__":
    main()