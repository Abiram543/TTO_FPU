<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

This project is a parameterized IEEE 754 Floating-Point Unit (FPU) designed for Tiny Tapeout, configured by default for half-precision (**FP16**: 1 sign bit, 5 exponent bits, and 10 mantissa bits = 16 bits total). The design executes high-precision floating-point **addition** and **subtraction** inside a single 1×1 tile on the SkyWater 130nm process with **42.9% cell utilization** and zero timing violations at 25 MHz.

Because Tiny Tapeout tiles provide only 8 dedicated digital inputs (`ui_in`) and 8 dedicated digital outputs (`uo_out`), the design integrates a byte-serial communication protocol over an 8-bit bidirectional data bus (`uio`):

1. **Operand Loading:** The host writes two 16-bit operands (`A` and `B`) byte-by-byte (least-significant byte first) over `uio_in` using the `write_en` (`ui_in[0]`) strobe. A 2-bit write pointer tracks incoming bytes. Once all 4 bytes are received, `ready` (`uo_out[3]`) asserts.
2. **Execution:** The host pulses `start` (`ui_in[2]`) and selects the operation on `opcode` (`ui_in[3]`: `0 = Addition`, `1 = Subtraction`).
3. **Core Arithmetic:** The arithmetic core (`fpu_core`) evaluates special cases in `S_SPECIAL` (Infinity, NaN, Denormal, and Zero passthrough). For normal numbers, `S_OPERATION` performs magnitude comparison and operand swapping, barrel-shifter exponent alignment, 12-bit mantissa addition/subtraction, leading-zero count (LZC) normalization, and overflow/underflow handling in 3 clock cycles.
4. **Result Readout:** Upon completion, `done` (`uo_out[1]`) asserts and the result is latched in `result_reg`. The host asserts `read_en` (`ui_in[1]`) to output the lower byte onto `uio_out` (`uio_oe` drives `0xFF`). The falling edge of `read_en` advances the internal read pointer to present the upper byte.

### Pinout Mapping

| Pin | Type | Signal | Function |
| :--- | :--- | :--- | :--- |
| `ui_in[0]` | Input | `write_en` | Active-high pulse to write one byte from `uio_in` |
| `ui_in[1]` | Input | `read_en` | Active-high level to drive `uio_out`; falling edge advances read pointer |
| `ui_in[2]` | Input | `start` | Active-high pulse to trigger computation (when `ready == 1`) |
| `ui_in[3]` | Input | `opcode` | Sampled on start: `0 = Addition`, `1 = Subtraction` |
| `ui_in[7:4]`| Input | `_unused` | Unused control pins (tied off internally) |
| `uo_out[0]` | Output | `busy` | High while arithmetic core is computing |
| `uo_out[1]` | Output | `done` | Latched high upon calculation complete |
| `uo_out[2]` | Output | `error` | High if inputs are invalid (Infinity, NaN, or unsupported Denormals) |
| `uo_out[3]` | Output | `ready` | High once all 4 operand bytes are loaded |
| `uo_out[7:4]`| Output | `wr_ptr[3:0]` | Current write pointer (debug tracking) |
| `uio[7:0]` | In/Out | `uio_in` / `uio_out` | Little-endian data bus (operands in / result out) |

---

## How to test

### Manual Testing Protocol (e.g. on FPGA or Commander / Microcontroller)

To perform `1.5 + 2.25 = 3.75`:
- `A = 1.5` → `0x3E00` (Low: `0x00`, High: `0x3E`)
- `B = 2.25` → `0x4080` (Low: `0x80`, High: `0x40`)
- Expected Result: `3.75` → `0x4380` (Low: `0x80`, High: `0x43`)

1. **Reset:** Assert `rst_n` low for at least 1 clock cycle, then release high (`ui_in = 0x00`).
2. **Write A Low:** Set `uio_in = 0x00`, pulse `ui_in[0]` high → low.
3. **Write A High:** Set `uio_in = 0x3E`, pulse `ui_in[0]` high → low.
4. **Write B Low:** Set `uio_in = 0x80`, pulse `ui_in[0]` high → low.
5. **Write B High:** Set `uio_in = 0x40`, pulse `ui_in[0]` high → low.
   - Observe `uo_out[3]` (`ready`) asserts high (`uo_out` lower nibble = `0x8`).
6. **Trigger Addition:** Set `ui_in = 0x04` (`start=1, opcode=0`), then return `ui_in = 0x00`.
   - Observe `uo_out[0]` (`busy`) pulses high, followed by `uo_out[1]` (`done`) asserting high.
7. **Read Low Byte:** Set `ui_in[1] = 1` (`read_en = 1`). Read `uio_out = 0x80`.
8. **Advance and Read High Byte:** Drop `ui_in[1] = 0` (advances pointer), then assert `ui_in[1] = 1`. Read `uio_out = 0x43`.
9. The combined 16-bit result is `0x4380` (3.75 in FP16).

---
