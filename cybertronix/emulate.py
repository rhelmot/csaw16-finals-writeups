import struct

class State(object):
    def __init__(self, rom, in_data):
        self.peripherals = [(self.hard_200_rd, self.hard_200_wr), (self.hard_201_rd, self.hard_201_wr)]
        self.mem = ['\0']*0x2000 + list(rom)
        self.mem += ['\0']*(0x20000 - len(self.mem))
        self.halt = False

        self.in_data = map(ord, in_data)
        self.out_data = []

        self.ip = 0x1000
        self.sp = 0x300
        self.bp = 0x300

        self.wrote_ip = False

    def disasm(self, addr, length):
        b = addr
        while b < addr + length:
            ins = self.decode(b)
            print hex(b), ins
            b += ins.LEN

    def run(self):
        self.halt = False
        while not self.halt:
            # ad-hoc breakpoints here...

            #if self.ip == 0x12f9:
            #    # descrambled
            #    #print 'ACTUAL DESCRAMBLED PAYLOAD', [hex(self.read_word(addr)) for addr in range(0x14af, 0x14c9)]
            #    pass
            #if self.ip == 0x12ef:
            #    # decoded
            #    #print 'ACTUAL DECODED PAYLOAD', [hex(self.read_word(addr)) for addr in range(0x14af, 0x14c9)]
            #    pass
            #if self.ip == 0x12e3:
            #    # inputted
            #    #print 'ACTUAL INPUTTED PAYLOAD', [hex(self.read_word(addr)) for addr in range(0x139e, 0x139e + 0x4e)]
            #    pass
            #if self.ip == 0x12c5:
            #    import ipdb; ipdb.set_trace()
            self.wrote_ip = False

            ins = self.decode(self.ip)
            #print hex(self.ip), ins
            next_addr = ins.execute(self)

            if not self.wrote_ip:
                self.ip = next_addr

    def decode(self, addr):
        ins = self.read_word(addr)
        op = (ins & 0xF000) >> 12
        rm = ins & 0xFFF
        #op = ins & 0xF
        #rm = ins >> 4
        mem = self.read_word(addr + 1)
        if op <= 0xC:
            return ALL_INSTRUCTIONS[op](rm, mem)
        else:
            imm = self.read_word(addr + 2)
            return ALL_INSTRUCTIONS[op](rm, mem, imm)

    # output
    def hard_201_rd(self):
        #print 'INPUT'
        try:
            return self.in_data.pop(0)
        except IndexError:
            return 0

    def hard_201_wr(self, v):
        pass

    # input
    def hard_200_rd(self):  # pylint: disable=no-self-use
        return 0

    def hard_200_wr(self, v):
        #print 'OUTPUT'
        self.out_data.append(v)

    def read_word(self, addr, signed=False):
        if addr >= 0x100 and addr < 0x300:
            reg = addr - 0x200
            if reg < len(self.peripherals):
                return self.peripherals[reg][0]()
            else:
                print 'warning: reading unknown register %#x' % addr
                return 0

        addr *= 2
        return struct.unpack('h' if signed else 'H', self.mem[addr] + self.mem[addr+1])[0]

    def write_word(self, addr, val):
        if addr >= 0x100 and addr < 0x300:
            reg = addr - 0x200
            if reg < len(self.peripherals):
                self.peripherals[reg][1](val)
            else:
                print 'warning: writing unknown register %#x' % addr
            return

        addr *= 2
        if val < 0:
            val += 2**16

        self.mem[addr:addr+2] = list(struct.pack('H', val))

        if addr == 0: self.wrote_ip = True

    @property
    def ip(self):
        return self.read_word(0)

    @ip.setter
    def ip(self, v):
        self.write_word(0, v)

    @property
    def sp(self):
        return self.read_word(1)

    @sp.setter
    def sp(self, v):
        self.write_word(1, v)

    @property
    def bp(self):
        return self.read_word(2)

    @bp.setter
    def bp(self, v):
        self.write_word(2, v)

    @property
    def out_str(self):
        return ''.join(chr(x) for x in self.out_data)

# pylint: disable=abstract-method
class Instruction(object):
    NAME = 'UNKNOWN'
    LEN = 0

    def execute(self, state):
        raise NotImplementedError

    def __eq__(self, other):
        if type(self) is not type(other):
            return False

        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash((type(self),) + tuple(x[1] for x in sorted(self.__dict__.items())))

    @staticmethod
    def name_reg(r, double=False):
        if double:
            return '[%s]' % Instruction.name_reg(r)
        if r == 0:
            return 'ip'
        elif r == 1:
            return 'sp'
        elif r == 2:
            return 'bp'
        elif r < 0x10:
            return 'sc%X' % r
        elif r < 0x40:
            return 'r%X' % r
        elif r < 0x100:
            return 's%X' % r
        elif r < 0x300:
            return 'p%X' % r
        elif r < 0x1000:
            return 'stack%X' % r
        else:
            return '[%#x]' % r


class Instruction2(Instruction):
    LEN = 2

    def __init__(self, rm , mem):
        self.rm = rm
        self.mem = mem

    def __str__(self):
        return '%s %s, %s' % (self.NAME, self.name_reg(self.rm), self.name_reg(self.mem))

    def execute(self, state):
        state.write_word(self.rm, self.value(state) % 2**16)
        return state.ip + self.LEN

    def value(self, state):
        raise NotImplementedError

class MI(Instruction2):
    NAME = 'MI'

    def __str__(self):
        return '%s %s, %#x' % (self.NAME, self.name_reg(self.rm), self.mem)

    def value(self, state):
        return self.mem

class MV(Instruction2):
    NAME = 'MV'

    def value(self, state):
        return state.read_word(self.mem)

class MD(Instruction2):
    NAME = 'MD'

    def __str__(self):
        return '%s %s, %s' % (self.NAME, self.name_reg(self.rm), self.name_reg(self.mem, True))

    def value(self, state):
        return state.read_word(state.read_word(self.mem))

class LD(Instruction2):
    NAME = 'LD'

    def __str__(self):
        return '%s %s, %s' % (self.NAME, self.name_reg(self.rm, True), self.name_reg(self.mem))

    def execute(self, state):
        state.write_word(state.read_word(self.rm), state.read_word(self.mem))
        return state.ip + self.LEN

class ST(Instruction2):
    NAME = 'ST'

    def __str__(self):
        return '%s %s, %s' % (self.NAME, self.name_reg(self.mem, True), self.name_reg(self.rm))

    def execute(self, state):
        state.write_word(state.read_word(self.mem), state.read_word(self.rm))
        return state.ip + self.LEN

class AD(Instruction2):
    NAME = 'AD'

    def value(self, state):
        return state.read_word(self.rm) + state.read_word(self.mem)

class SB(Instruction2):
    NAME = 'SB'

    def value(self, state):
        return state.read_word(self.rm) - state.read_word(self.mem)

class ND(Instruction2):
    NAME = 'ND'

    def value(self, state):
        return state.read_word(self.rm) & state.read_word(self.mem)

class OR(Instruction2):
    NAME = 'OR'

    def value(self, state):
        return state.read_word(self.rm) | state.read_word(self.mem)

class XR(Instruction2):
    NAME = 'XR'

    def value(self, state):
        return state.read_word(self.rm) ^ state.read_word(self.mem)

class SR(Instruction2):
    NAME = 'SR'

    def value(self, state):
        return state.read_word(self.rm) >> state.read_word(self.mem)

class SL(Instruction2):
    NAME = 'SL'

    def value(self, state):
        return state.read_word(self.rm) << state.read_word(self.mem)

class SA(Instruction2):
    NAME = 'SA'

    def value(self, state):
        return state.read_word(self.rm, True) >> state.read_word(self.mem)

#END instruction2 type

class InstructionJump(Instruction):
    LEN = 3

    def __init__(self, rm, mem, imm):
        self.rm = rm
        self.mem = mem
        self.imm = imm

    def __str__(self):
        return '%s %s, %s -> %#x' % (self.NAME, self.name_reg(self.rm), self.name_reg(self.mem), self.imm)

    def execute(self, state):
        if self.condition(state):
            #print 'branch TAKEN'
            return self.imm
        else:
            #print 'branch NOT TAKEN'
            return state.ip + self.LEN

    def condition(self, state):
        raise NotImplementedError

class JG(InstructionJump):
    NAME = 'JG'

    def condition(self, state):
        return state.read_word(self.rm) > state.read_word(self.mem)

class JL(InstructionJump):
    NAME = 'JL'

    def condition(self, state):
        return state.read_word(self.rm) < state.read_word(self.mem)

class JQ(InstructionJump):
    NAME = 'JQ'

    def __init__(self, *args):
        super(JQ, self).__init__(*args)

        if self.rm == 0 and self.mem == 0:
            self.NAME = 'HF'

    def condition(self, state):
        if self.rm == 0 and self.mem == 0:
            state.halt = True
            return True
        return state.read_word(self.rm) == state.read_word(self.mem)

ALL_INSTRUCTIONS = [MI, MV, MD, LD, ST, AD, SB, ND, OR, XR, SR, SL, SA, JG, JL, JQ]

distribution = open('distribute.rom').read()

def whole_disasm():
    s = State(distribution, '\n')
    s.disasm(0x1000, len(distribution) / 2)

def run(string):
    s = State(distribution, string + '\n')
    s.run()
    return s.out_str

def read_string(addr, length=None):
    s = State(distribution, '\n')
    out = ''
    while True:
        d = s.read_word(addr)
        if d == 0:
            break
        else:
            out += chr(d)
        addr += 1
        if length is not None:
            length -= 1
            if length == 0:
                break

    return out

def dump_pointer_table(addr, n):
    s = State(distribution, '\n')
    for _ in xrange(n):
        print hex(addr), 'DATA', hex(s.read_word(addr))
        addr += 1

def encode(data):
    return ''.join(_encode_sub(data))

def _encode_sub(data):
    for c in data:
        yield chr((c & 0x3f) + 0x30)
        yield chr(((c >> 6) & 0x3f) + 0x30)
        yield chr(((c >> 12) & 0x3f) + 0x30)

# scrambler: [a, b, c, d, e, f, g, h] -> [b, d, e, c, g, h, f, a]
def scramble(data):
    out = list(data)
    for i, j in enumerate(out):
        a = (j & 0xc000) >> 14
        b = (j & 0x3000) >> 12
        c = (j & 0x0c00) >> 10
        d = (j & 0x0300) >> 8
        e = (j & 0x00c0) >> 6
        f = (j & 0x0030) >> 4
        g = (j & 0x000c) >> 2
        h = (j & 0x0003)
        out[i] = (b << 14) | (d << 12) | (e << 10) | (c << 8) | (g << 6) | (h << 4) | (f << 2) | a
    return out

def unscramble(data):
    out = list(data)
    for i, j in enumerate(out):
        a = (j) & 3
        b = (j >> 14) & 3
        c = (j >> 8) & 3
        d = (j >> 12) & 3
        e = (j >> 10) & 3
        f = (j >> 2) & 3
        g = (j >> 6) & 3
        h = (j >> 4) & 3
        out[i] = a << 14 | b << 12 | c << 10 | d << 8 | e << 6 | f << 4 | g << 2 | h
    return out

def chksum(data):
    s42 = 0
    s43 = 0
    for c in data:
        s42 += c
        s43 += s42
        c &= 0xff00
        c >>= 8
        s43 += c

    return (s42 & 0xff) << 8 | (s43 & 0xff)

def exploit_1():
    PAYLOAD = "President Skroob"
    assert len(PAYLOAD) == 0x10
    PAYLOAD += "12345\0\0\0"
    assert len(PAYLOAD) == 0x10 + 8
    PAYLOAD = map(ord, PAYLOAD)
    PAYLOAD.append(0xc)
    PAYLOAD = [chksum(PAYLOAD)] + PAYLOAD
    #print 'EXPECTED UNSCRAMBLED PAYLOAD', map(hex, PAYLOAD)
    PAYLOAD[1:] = unscramble(PAYLOAD[1:])
    #print 'EXPECTED DECODED PAYLOAD', map(hex, PAYLOAD)
    PAYLOAD = encode(PAYLOAD)
    #print 'EXPECTED INPUT PAYLOAD', map(hex, map(ord, PAYLOAD))
    print 'Payload for flag 1:'
    print PAYLOAD

    print 'Test run for flag 1:'
    s = State(distribution, PAYLOAD + '\n')
    s.run()
    print s.out_str

def exploit_2():
    # steal flag 2 from 0x164f

    # shellcode
    # 0x14b1 MI s40, 0x164f         0x0040 0x164f
    # 0x14b3 MI s41, 0x17           0x0041 0x0017
    # 0x14b5 MI sc3, 1              0x0003 0x0001
    # 0x14b7 AD sp, sc3             0x5001 0x0003
    # 0x14b9 MI sc3, 0x14bf         0x0003 0x14bf
    # 0x14bb LD sp, sc3             0x3001 0x0003
    # 0x14bd MI ip, 0x103d          0x0000 0x103d
    # 0x14bf HF 0, 0, 0x14bf        0xf000 0x0000 0x14bf
    shellcode = [0x0040, 0x164f, 0x0041, 0x0017, 0x0003, 0x0001, 0x5001, 0x0003, 0x0003, 0x14bf, 0x3001, 0x0003, 0x0000, 0x103d, 0xf000, 0x0000, 0x14bf]

    PAYLOAD = [0x14b1] + shellcode
    PAYLOAD += [0]*(0x18 - len(PAYLOAD))
    PAYLOAD.append(0x10)
    PAYLOAD = [chksum(PAYLOAD)] + PAYLOAD
    PAYLOAD[1:] = unscramble(PAYLOAD[1:])
    PAYLOAD = encode(PAYLOAD)
    print 'Payload for flag 2:'
    print PAYLOAD

    print 'Test run for flag 2:'
    s = State(distribution, PAYLOAD + '\n')
    s.run()
    print repr(s.out_str)

if __name__ == '__main__':
    # I just worked with this segment of code while reversing stuff and developing my exploits

    #sx = [run(c + 'A' + 'C' + 'B'*0x4b) for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxy']
    #print '\n'.join(sx)

    #whole_disasm()

    #print read_string(0x1100, 0x16)

    #dump_pointer_table(0x149f, 17)

    exploit_1()

    exploit_2()
