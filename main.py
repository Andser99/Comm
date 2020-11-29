import socket
import CustomPacket
import threading
import time
import struct

CurrentSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
IsOpen = True
CurrentIP = ""
CurrentPort = 0
LastPacketTime = time.time()
ReceivedList = []
CurrentSequence = 0
MaxPacketSize = 1024
AckList = {}
CommBuffer = {}
ResponseAddress = None

ReceivedAcks = []

#struct.pack('hcchhh',)

def main():
    global MaxPacketSize
    print("Max packet size: ")
    MaxPacketSize = int(input())
    print("send/receive: ")
    inp = input()
    port = 0
    sender = False
    if inp == "send":
        sender = True
    elif inp == "receive":
        sender = False

    if sender:
        waitForSending()
    else:
        waitAsReceiver()

    print(f'a')


def waitAsReceiver():
    global CurrentIP
    global CurrentPort
    global ReceivedList
    global LastPacketTime

    print("Address and port {<address> <port>}:")
    inp = input().split(" ") #ip , port
    CurrentIP = inp[0]
    CurrentPort = int(inp[1])
    CommBuffer.clear()
    #CurrentSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    CurrentSocket.bind((CurrentIP, int(CurrentPort)))
    while True:
        global ResponseAddress
        rec, address = CurrentSocket.recvfrom(4096)
        ResponseAddress = address
        length = rec[0]*256 + rec[1]
        if length + 10 != len(rec):
            print("Length in header doesn't match packet length")
            continue
        header_rest = bytes(rec[2:10])
        unpacked = struct.unpack("!cchhh",header_rest)
        LastPacketTime = time.time()
        data = None
        if int(length) > 0:
            data = bytes(rec[10:int(length)+10])
        pkt = CustomPacket.CustomPacket(int(length),
                                                      unpacked[0],
                                                      unpacked[1],
                                                      unpacked[2],
                                                      unpacked[3],
                                                      unpacked[4],
                                                      data)
        if pkt.valid:
            ## If its an ack to keep alive, just reset last packet time
            if pkt.flags == 0b00000101:
                LastPacketTime = time.time()
            else:
                if pkt.sequence not in CommBuffer.keys():
                    CommBuffer[pkt.sequence] = pkt
                ReconstructBuffer()
                ackPacket = CustomPacket.CustomPacket(0, 0, unpacked[1], unpacked[2], unpacked[3])
                ackPacket.setFlags("A")
                print(f"Sending ack for {unpacked[2]}")
                send(ackPacket.pack())
        else:
            print("Invalid packet!")

def ReconstructBuffer():
    print("..Start Reconstruction Attempt..")
    global CommBuffer
    if len(CommBuffer) == 0:
        print("..Empty Buffer, ending reconstruction attempt..")
        return
    length = 0
    ordered = sorted(CommBuffer.values(), key=lambda x: x.sequence)
    isText = False
    for x in ordered:
        isText = x.pkt_type == b'\x02'
        length = x.sequence_len
    seq_count = len(ordered)
    seq_len = ordered[0].sequence_len
    IsAscending = True
    fragmentString = f"{ordered[0].sequence}: {ordered[0].data}\n"
    for x in range(len(ordered)-1):
        fragmentString += f"{ordered[x+1].sequence}: {ordered[x+1].data}\n"
        if ordered[x].sequence + 1 != ordered[x+1].sequence:
            IsAscending = False
    print(fragmentString, end='')
    if IsAscending and seq_count == seq_len + 1:
        print("Reconstruction Successful")
        data = "Message: "
        for x in ordered:
            data += x.data.decode("utf-8")
        print(data)
        CommBuffer.clear()
    else:
        print(f"Missing {seq_len - (seq_count - 1)} fragments")
    print("..End Reconstruction Attempt..")



def waitForReceive():
    global CurrentIP
    global CurrentPort
    global CurrentSocket
    global ReceivedList
    global LastPacketTime
    global AckList
    ReceivedList.clear()
    #CurrentSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    #CurrentSocket.bind((CurrentIP, int(CurrentPort)))
    #AckList[4] = False ##DEBUG
    #AckList[3] = False ##DEBUG
    while True:
        rec = CurrentSocket.recv(4096)
        length = rec[0]*256 + rec[1]
        if length + 10 != len(rec):
            print("Length in header doesn't match packet length")
            continue
        header_rest = bytes(rec[2:10])
        unpacked = struct.unpack("!cchhh",header_rest)
        data = None
        if int(length) > 0:
            data = bytes(rec[10:int(length)+10])
        LastPacketTime = time.time()
        pkt = CustomPacket.CustomPacket(int(length),
                                                      unpacked[0],
                                                      unpacked[1],
                                                      unpacked[2],
                                                      unpacked[3],
                                                      unpacked[4],
                                                      data)
        if pkt.valid:
            ReceivedList.append(pkt)
            ## check if theres a pending ack with that sequence number
            ackIndex = -1
            if len(ReceivedList) > 0:
                ackIndex = (pkt.sequence in AckList.keys() and pkt.sequence_len == len(AckList))
            if  ackIndex:
                AckList[ackIndex] = True
        else:
            print("Invalid packet!")
        print(f"Received; {int(length)}")
        print('Unpacked data: ', unpacked)
        print('Message/Data: ', data)
    return

def startKeepAlive():
    thread = threading.Thread(target=keepAliveFunction)
    thread.start()

def keepAliveFunction():
    global CurrentSocket
    global CurrentIP
    global CurrentPort
    while True:
        if time.time() - LastPacketTime > 3:
            CurrentSocket.sendto(CustomPacket.keepAlive(), (CurrentIP, CurrentSocket))
            time.sleep(2.95)
        time.sleep(0.05)
        if time.time() - LastPacketTime > 15:
            CurrentSocket.close()


def waitForSending():
    global CurrentIP
    global CurrentPort
    global CurrentSocket
    global ResponseAddress
    print("Address and port {<address> <port>}:")
    inp = input().split(" ") #ip , port
    CurrentSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    CurrentIP = inp[0]
    CurrentPort = int(inp[1])
    ResponseAddress = (CurrentIP, CurrentPort)
    t = threading.Thread(target=waitForReceive, args=())
    init = False
    inp = input().split(' ')
    while inp != "q":
        if inp[0] == "f":
            sendFile(inp[1])
        elif inp[0] == "t":
            sendText(inp[1])
        inp = input().split(" ")
        if not init:
            t.start()
            init = True
    return False


    #<IP> <Socket> <type> <message>

def sendText(text):
    global CurrentSequence
    global MaxPacketSize
    global ReceivedList
    global AckList
    data = []
    textLength = len(bytes(text, encoding="UTF-8"))
    acknowledgedAll = False
    if textLength > MaxPacketSize:
        data = text.encode()[::MaxPacketSize]
    else:
        data.append(text.encode())
    print("data: ", data)
    listToSend = []
    #Create packets to be sent and setup acknowledgment list
    if CurrentSequence + len(data) > 65535:
        CurrentSequence = 0
    for x in data:
        listToSend.append(CustomPacket.CustomPacket(len(x), 0, b'\x02', CurrentSequence, len(data)-1, None, data))
        CurrentSequence += 1
    AckList.clear()
    for x in listToSend:
        AckList[x.sequence] = False
    while not acknowledgedAll:
        i = 0
        unackCount = 0
        for x in AckList:
            if not AckList[x]:
                unackCount += 1
                send(listToSend[i].pack())
            i += 1
        timeToSleep = 0.2
        if (0.001 * unackCount < timeToSleep):
            timeToSleep = 0.001 * unackCount
        time.sleep(timeToSleep)
    return


def sendFile(path):
    return


def send(byteData):
    print (f"sending {byteData}")
    global CurrentIP
    global CurrentSocket
    global CurrentPort
    global IsOpen
    global ResponseAddress
    if IsOpen:
        CurrentSocket.sendto(byteData, ResponseAddress)
    else:
        CurrentSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        CurrentSocket.sendto(byteData, ResponseAddress)
        IsOpen = True

if __name__ == '__main__':
    main()

