import struct
import crcmod
import random

#returns a packed endComm packet
def endComm():
    pckEnd = CustomPacket(0, b'\x02', b'\x00', 0, 0, None, None)
    return pckEnd.pack()
#returns a packed endComm packet
def endCommAck():
    pckEnd = CustomPacket(0, b'\x06', b'\x00', 0, 0, None, None)
    return pckEnd.pack()
#returns a packed keepAlive packet
def keepAlive():
    pckKeep = CustomPacket(0, b'\x01', b'\x00', 0, 0, None, None)
    return pckKeep.pack()
#returns a packed acknowledge for a keepAlive packet
def keepAliveAck():
    pckKeep = CustomPacket(0, b'\x05', b'\x00', 0, 0, None, None)
    return pckKeep.pack()

class CustomPacket:
    def __init__(self, pkt_length, flags, pkt_type, sequence, sequence_len, checksum=None, data=None):
        self.pkt_length = pkt_length
        if isinstance(flags, bytes):
            self.flags = flags
        else:
            self.flags = flags.to_bytes(1, byteorder="big")
        self.pkt_type = pkt_type
        self.sequence = sequence
        self.sequence_len = sequence_len
        self.data = data
        if checksum is not None:
            self.calculateChecksum()
            if self.pkt_length == 11 and random.random() > 0.5:
                self.valid = False
                print(f"simulating invalid packet with seq: {sequence} {data}")
            else:
                self.valid = (checksum == self.checksum)
        else:
            self.calculateChecksum()
            self.valid = True


    def calculateChecksum(self):
        crc16 = crcmod.mkCrcFun(0x11021, rev=False, initCrc=0x0000, xorOut=0x0000)
        x = crc16(self.packForChecksum())
        if random.random() > 1:
            self.checksum = 1234
        else:
            self.checksum = x

    def pack(self):
        packed = struct.pack('!hccHHH', self.pkt_length, self.flags, self.pkt_type, self.sequence, self.sequence_len, self.checksum)
        if self.data is not None:
            packed += self.data
        return packed

    def packForChecksum(self):
        if self.sequence_len > 65535:
            print("Size exceeded protocol limits")
        packed = struct.pack('!hccHH', self.pkt_length, self.flags, self.pkt_type, self.sequence, self.sequence_len)
        if self.data is not None:
            packed += self.data
        return packed

    def print(self):
        print(f"Packet {self.sequence}")
        print(f"    flags: {self.flags}")
        print(f"    type: {self.pkt_type}")
        print(f"    seq_len: {self.sequence_len}")
        print(f"    checksum: {self.checksum}")
        print(f"    data:{self.data}")

    #AEK --0000 0111
    def setFlags(self, flags):
        for x in flags:
            if x == "A":
                self.flags = b'\x04'
            elif x == "K":
                self.flags = b'\x01'
            elif x == "AK":
                self.flags = b'\x05'
            elif x == "E":
                self.flags = b'\x02'
            elif x == "EA":
                self.flags = b'\x06'
        self.calculateChecksum()


