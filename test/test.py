# SPDX-FileCopyrightText: © 2024 Your Name
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles


def get_int(sig):
    """Safely read a signal value, returning 0 if X/Z (for GL sim)."""
    try:
        return sig.value.integer
    except ValueError:
        return 0


async def reset_dut(dut):
    """Apply reset and initialize all inputs."""
    dut.rst_n.value = 0
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)


async def write_byte(dut, data):
    """Write one operand byte: set data on uio_in, pulse write_en."""
    dut.uio_in.value = data
    dut.ui_in.value = 0x01          # write_en = 1
    await ClockCycles(dut.clk, 3)   # edge detector needs 2 cycles + margin
    dut.ui_in.value = 0x00          # write_en = 0
    await ClockCycles(dut.clk, 3)   # settle


async def load_operands(dut, op_a_hex, op_b_hex):
    """Load two FP16 operands byte-by-byte (little-endian)."""
    await write_byte(dut, op_a_hex & 0xFF)          # A low byte
    await write_byte(dut, (op_a_hex >> 8) & 0xFF)   # A high byte
    await write_byte(dut, op_b_hex & 0xFF)           # B low byte
    await write_byte(dut, (op_b_hex >> 8) & 0xFF)    # B high byte


async def start_and_wait(dut, opcode):
    """Pulse start with opcode (0=ADD, 1=SUB), wait for done."""
    val = 0x04 | (opcode << 3)      # bit[2]=start, bit[3]=opcode
    dut.ui_in.value = val
    await ClockCycles(dut.clk, 3)
    dut.ui_in.value = 0x00
    # Wait for done (bit 1 of uo_out)
    for _ in range(20):
        await ClockCycles(dut.clk, 1)
        if get_int(dut.uo_out) & 0x02:
            break


async def read_result(dut):
    """Read 2-byte FP16 result via uio_out, return as 16-bit int."""
    # Read low byte
    dut.ui_in.value = 0x02          # read_en = 1
    await ClockCycles(dut.clk, 3)
    low = get_int(dut.uio_out)

    # Falling edge advances rd_ptr
    dut.ui_in.value = 0x00          # read_en = 0
    await ClockCycles(dut.clk, 3)

    # Read high byte
    dut.ui_in.value = 0x02          # read_en = 1
    await ClockCycles(dut.clk, 3)
    high = get_int(dut.uio_out)

    dut.ui_in.value = 0x00
    await ClockCycles(dut.clk, 3)

    return (high << 8) | low


# =====================================================================
# Test Cases
# =====================================================================

@cocotb.test()
async def test_add_normal(dut):
    """Test: 1.5 + 2.25 = 3.75 (0x3E00 + 0x4080 = 0x4380)"""
    clock = Clock(dut.clk, 40, units="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    await load_operands(dut, 0x3E00, 0x4080)
    await start_and_wait(dut, opcode=0)     # ADD

    result = await read_result(dut)
    dut._log.info(f"1.5 + 2.25 = 0x{result:04X} (expected 0x4380)")
    assert result == 0x4380, f"ADD failed: got 0x{result:04X}, expected 0x4380"


@cocotb.test()
async def test_sub_cancel(dut):
    """Test: 5.0 - 5.0 = +0.0 (0x4500 - 0x4500 = 0x0000)"""
    clock = Clock(dut.clk, 40, units="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    await load_operands(dut, 0x4500, 0x4500)
    await start_and_wait(dut, opcode=1)     # SUB

    result = await read_result(dut)
    dut._log.info(f"5.0 - 5.0 = 0x{result:04X} (expected 0x0000)")
    assert result == 0x0000, f"SUB cancel failed: got 0x{result:04X}, expected 0x0000"


@cocotb.test()
async def test_inf_error(dut):
    """Test: Inf input triggers error flag (0x7C00 = +Inf)"""
    clock = Clock(dut.clk, 40, units="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    await load_operands(dut, 0x7C00, 0x3C00)   # Inf + 1.0
    await start_and_wait(dut, opcode=0)

    status = get_int(dut.uo_out)
    error = (status >> 2) & 1
    done  = (status >> 1) & 1
    dut._log.info(f"Inf + 1.0: done={done}, error={error}")
    assert error == 1, "Expected error flag for Inf input"
    assert done == 1, "Expected done flag"


@cocotb.test()
async def test_zero_passthrough(dut):
    """Test: 3.0 + 0.0 = 3.0 (0x4200 + 0x0000 = 0x4200)"""
    clock = Clock(dut.clk, 40, units="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    await load_operands(dut, 0x4200, 0x0000)
    await start_and_wait(dut, opcode=0)

    result = await read_result(dut)
    dut._log.info(f"3.0 + 0.0 = 0x{result:04X} (expected 0x4200)")
    assert result == 0x4200, f"Zero passthrough failed: got 0x{result:04X}, expected 0x4200"


@cocotb.test()
async def test_back_to_back(dut):
    """Test consecutive operations without reset."""
    clock = Clock(dut.clk, 40, units="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    # Op 1: 1.0 + 1.0 = 2.0 (0x3C00 + 0x3C00 = 0x4000)
    await load_operands(dut, 0x3C00, 0x3C00)
    await start_and_wait(dut, opcode=0)
    r1 = await read_result(dut)
    dut._log.info(f"Op1: 1.0 + 1.0 = 0x{r1:04X} (expected 0x4000)")
    assert r1 == 0x4000, f"Op1 failed: 0x{r1:04X}"

    # Op 2: 10.0 - 2.0 = 8.0 (0x4900 - 0x4000 = 0x4800)
    await load_operands(dut, 0x4900, 0x4000)
    await start_and_wait(dut, opcode=1)
    r2 = await read_result(dut)
    dut._log.info(f"Op2: 10.0 - 2.0 = 0x{r2:04X} (expected 0x4800)")
    assert r2 == 0x4800, f"Op2 failed: 0x{r2:04X}"

