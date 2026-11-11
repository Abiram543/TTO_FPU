![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg) ![](../../workflows/fpga/badge.svg)

# Parameterized IEEE 754 Floating-Point Unit (FPU) for Tiny Tapeout

A high-efficiency, parameterized IEEE 754 Floating-Point Unit (FPU) supporting **Addition** and **Subtraction**, tailored for physical fabrication on a single 1×1 tile (167 µm × 108 µm) via the Tiny Tapeout multi-project wafer framework.

---

## 📌 Project Overview

Digital implementation of floating-point arithmetic on micro-silicon tiles is heavily constrained by pin count and silicon area. This design solves both challenges:
- **I/O Bottleneck:** Tiny Tapeout provides 8 dedicated digital inputs and 8 dedicated outputs. A clean **little-endian byte-serial protocol** enables wide operand transmission over an 8-bit bidirectional data bus (`uio`).
- **Area Efficiency:** By utilizing a mostly-combinational arithmetic pipeline sequenced by a compact 3-state FSM, the design achieves **42.9% core cell utilization** on SkyWater 130nm, leaving ample routing margin with zero setup/hold timing violations at 25 MHz.
- **Architectural Parameterization:** Although fabricated in **FP16** (half-precision), the underlying Verilog core is fully parameterized by `EXP_W` and `MAN_W`, making it instantly reusable for **FP8 (E4M3 / E5M2)**, **BF16**, **FP32**, or **FP64** multi-tile tapeouts.

---

## 🔬 Floating-Point Representation (FP16 Default)

The default configuration implements IEEE 754 Half-Precision Floating-Point:

$$\text{Value} = (-1)^{\text{Sign}} \times 2^{\text{Exponent} - 15} \times (1.\text{Mantissa})$$(https://twitter.com/tinytapeout)
  - Bluesky [@tinytapeout.com](https://bsky.app/profile/tinytapeout.com)
