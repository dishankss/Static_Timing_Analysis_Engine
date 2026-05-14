# TimingGraph: Static Timing Analysis Engine

A Python-based Static Timing Analysis (STA) engine for combinational digital circuits using `.bench` netlists and NLDM Liberty timing models.  

The project implements graph-based timing traversal, bilinear LUT interpolation, arrival/required time propagation, slack computation, and critical path extraction for large benchmark circuits.

---

## Features

- Parses combinational `.bench` netlists
- Parses NLDM Liberty timing libraries
- Builds graph-based fanin/fanout timing models
- Performs deque-based topological traversal
- Computes:
  - Arrival times
  - Required times
  - Slack values
  - Critical paths
- Supports bilinear interpolation for delay/slew lookup tables
- Handles multi-input gate delay scaling
- Implements timing-aware load capacitance modeling
- Optimized using:
  - Pre-parsed LUT caching
  - Reduced repeated timing lookups
  - Efficient BFS traversal

---

## Project Structure

```text
Static_Timing_Analysis_Engine/
├── STA.py
├── requirements.txt
├── sample_inputs/
│   ├── c17.bench
│   └── sample_NLDM.lib
├── outputs/
│   ├── ckt_details.txt
│   ├── delay_LUT.txt
│   ├── slew_LUT.txt
│   └── ckt_traversal.txt
└── README.md
```

---

## Supported Analysis Flow

### Phase 1
- Circuit netlist parsing
- Liberty timing parsing
- LUT extraction
- Fanin/Fanout analysis

### Phase 2
- Topological traversal
- Forward STA propagation
- Backward required-time propagation
- Slack computation
- Critical path reconstruction

---

## Example Benchmark Statistics

Validated on benchmark circuits containing:

- 485 primary inputs
- 519 primary outputs
- 7K+ logic gates
- Thousands of timing arcs

---

## How to Run

### Generate circuit details

```bash
python3.7 STA.py --read_ckt c17.bench
```

### Generate delay LUTs

```bash
python3.7 STA.py --read_nldm sample_NLDM.lib --delays
```

### Generate slew LUTs

```bash
python3.7 STA.py --read_nldm sample_NLDM.lib --slews
```

### Run full STA flow

```bash
python3.7 STA.py --read_ckt c17.bench --read_nldm sample_NLDM.lib
```

---

## Generated Outputs

- `ckt_details.txt`
- `delay_LUT.txt`
- `slew_LUT.txt`
- `ckt_traversal.txt`

---

## Technical Concepts Used

- Static Timing Analysis (STA)
- Graph Traversal Algorithms
- Topological Sorting
- Bilinear Interpolation
- NLDM Liberty Timing Models
- Timing Graph Construction
- Load Capacitance Modeling
- Critical Path Analysis

---

## Technologies Used

- Python 3.7
- NLDM Liberty Models
- ISCAS Benchmark Circuits
- deque-based BFS Traversal
- Graph-Based Timing Analysis
