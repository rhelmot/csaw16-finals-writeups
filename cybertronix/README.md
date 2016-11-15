# Cybertronix 64k

This was a set of reversing/pwning challenges written by [Hypersonic](https://github.com/Hypersonic) and [ubsan](https://github.com/ubsan). We were given an emulator for a fictional 16-bit architecture along with a manual for the instruction set, a "scrubbed" ROM free of flags, and an address to connect to to run a copy of the "unscrubbed" ROM.

The following files were provided during the CTF:

- [`ct64_interpreter`](./ct64_interpreter): The provided emulator for the architecture
- [`distribute.rom`](./distribute.rom): The "scrubbed" ROM image
- [`CYBERT.pdf`](./CYBERT.pdf): The instruction set manual

The full source code for the program has since been [released](https://github.com/Hypersonic/CyberTronix64k).

- [`trace.gdb`](./trace.gdb): A gdb script to dump an instruction trace for a run of the program
- [`emulate.py`](./emulate.py): A python script implementing an emulator and disassembler for the architecture. Contains exploits for both flags at the bottom.
- [`disasm.log`](./disasm.log): My annotated disassembly of the provided ROM.

The first challenge was a reversing challenge - understand the instruction set and reverse engineer the checks being performed on the input data to jump to a function that prints the first flag.

The second challenge was a pwning challenge - find an off-by-one error in the function index check, use it to jump to shellcode that prints out the second flag.
