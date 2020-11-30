import struct


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
            self.valid = (checksum == self.checksum)
        else:
            self.calculateChecksum()
            self.valid = True


    def calculateChecksum(self):
        self.checksum = 1488

    def pack(self):
        kurva = self.flags
        #if isinstance(kurva, int):
        #    kurva = bytes([kurva])
        #    if kurva == 0:
        #        kurva = 0b00000000
        #elif len(kurva) == 0:
        #    kurva = 0b00000000
        packed = struct.pack('!hcchhh', self.pkt_length, kurva, self.pkt_type, self.sequence, self.sequence_len, self.checksum)
        if self.data is not None:
            packed += self.data[0]
        return packed

    def checkValidity(self):
        return self.checksum == 1488

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


