import socket
from os import system

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
IsKeepingAlive = False
DownloadedPath = "download/"
Verbose = False
SequenceOfLastReceived = -1
SeqLenOfLastReceived = 0
LastMessage = ""
IsReceiver = True

ReceivedAcks = []

#struct.pack('hcchhh',)

def main():
    global MaxPacketSize
    global DownloadedPath
    print("send/receive: ")
    inp = input()
    port = 0
    sender = False
    if inp == "send":
        sender = True
        print("Max fragment size (1..65535): ")
        MaxPacketSize = int(input())

    if sender:
        waitForSending()
    else:
        waitAsReceiver()

    print(f'End main')


def waitAsReceiver():
    global CurrentIP
    global CurrentPort
    global ReceivedList
    global LastPacketTime
    global IsKeepingAlive
    global IsReceiver
    global DownloadedPath
    global SeqLenOfLastReceived
    global SequenceOfLastReceived

    print("relative path for saving: ")
    DownloadedPath = input()
    if DownloadedPath == "":
        DownloadedPath = "download/"
    print("Address and port {<address> <port>}:")
    inp = input().split(" ") #ip , port
    CurrentIP = inp[0]
    CurrentPort = int(inp[1])
    CommBuffer.clear()
    #CurrentSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    CurrentSocket.bind((CurrentIP, CurrentPort))
    while IsReceiver:
        global ResponseAddress
        try:
            rec, address = CurrentSocket.recvfrom(4096)
        except:
            continue
        if ResponseAddress != address:
            print("Starting keepalive thread")
            SeqLenOfLastReceived = 0
            SequenceOfLastReceived = -1
            startKeepAlive()
        ResponseAddress = address
        length = rec[0]*256 + rec[1]
        if length + 10 != len(rec):
            print("Length in header doesn't match packet length")
            continue
        header_rest = bytes(rec[2:10])
        unpacked = struct.unpack("!ccHHH",header_rest)
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
            ## If its an ack to keep alive, just reset the last packet time
            if pkt.flags == b'\x05':
                LastPacketTime = time.time()
            elif pkt.flags == b'\x02':
                send(CustomPacket.endCommAck())
                stopKeepAlive()
            else:
                ackPacket = CustomPacket.CustomPacket(0, 0, unpacked[1], unpacked[2], unpacked[3])
                ackPacket.setFlags("A")
                if Verbose: print(f"Sending ack for {unpacked[2]}")
                send(ackPacket.pack())
                if pkt.sequence not in CommBuffer.keys():
                    CommBuffer[pkt.sequence] = pkt
                    ReconstructBuffer()
        else:
            if Verbose: print("Invalid packet!")
    CommBuffer.clear()
    CurrentSocket.close()

def clearBufferOfLast():
    global CommBuffer
    global SeqLenOfLastReceived
    global SequenceOfLastReceived
    ToRemove = []
    for x in CommBuffer.keys():
        if CommBuffer[x].sequence_len == SeqLenOfLastReceived and CommBuffer[x].sequence <= SequenceOfLastReceived:
            ToRemove.append(x)
    for x in ToRemove:
        if x in CommBuffer.keys():
            del CommBuffer[x]

IsBlockingKeepAlive = False
def ReconstructBuffer():
    global SequenceOfLastReceived
    global SeqLenOfLastReceived
    global LastMessage
    global IsReceiver
    global IsBlockingKeepAlive
    if Verbose: print("..Start Reconstruction Attempt..")
    global CommBuffer
    if len(CommBuffer) == 0:
        if Verbose: print("..Empty Buffer, ending reconstruction attempt..")
        return
    type = 0
    maxSeqLen = 0
    for x in CommBuffer.values():
        if x.sequence_len > maxSeqLen:
            maxSeqLen = x.sequence_len
            type = x.pkt_type
    if maxSeqLen < len(CommBuffer):
        if Verbose: print("not enough buffer values to reconstruct based on largest found sequence length")
        clearBufferOfLast()
    if ((len(CommBuffer) == maxSeqLen and maxSeqLen > 2) or len(CommBuffer) % 10 == 1): print(f"Fragments: {len(CommBuffer)}/{maxSeqLen+1}")
    if maxSeqLen > len(CommBuffer):
        return
    ordered = sorted(CommBuffer.values(), key=lambda x: x.sequence)
    if len(ordered) == 0: return
    isText = False
    isFile = False
    for x in ordered:
        isText = x.pkt_type == b'\x02'
        isFile = x.pkt_type == b'\x01'
        length = x.sequence_len
    seq_count = len(ordered)
    seq_len = ordered[0].sequence_len
    IsAscending = True
    system('cls')
    fragmentString = f"{ordered[0].sequence}: {ordered[0].data}\n"
    for x in range(len(ordered)-1):
        fragmentString += f"{ordered[x+1].sequence}: {ordered[x+1].data}\n"
        if ordered[x].sequence + 1 != ordered[x+1].sequence:
            IsAscending = False
    if Verbose: print(fragmentString, end='')
    if IsAscending and seq_count == seq_len + 1 and ordered[-1].sequence != SequenceOfLastReceived:
        if Verbose: print("Reconstruction Successful")
        if isText:
            data = "Message: "
            for x in ordered:
                if x.data is not None:
                    data += x.data.decode("utf-8")
            print(data)
            LastMessage = data
            CommBuffer.clear()
        elif isFile:
            savePath = DownloadedPath + "\\" + ordered[0].data.decode("utf-8")
            f = open(savePath, "wb")
            data = b''
            for x in ordered[1:]:
                if x.data is not None:
                    data += x.data
            f.write(data)
            f.close()
            print(f"File saved at {savePath}")
            CommBuffer.clear()
        SequenceOfLastReceived = ordered[-1].sequence
        SeqLenOfLastReceived = ordered[-1].sequence_len
        print("Switch to sender? y/n")
        IsBlockingKeepAlive = True
        if input() == "y":
            IsReceiver = False
            stopKeepAlive()
            CurrentSocket.close()
            IsBlockingKeepAlive = False
            waitForSending()
        IsBlockingKeepAlive = False


    else:
        if Verbose: print(f"Missing {seq_len - (seq_count - 1)} fragments")
    if Verbose: print("..End Reconstruction Attempt..")
    #if seq_count > seq_len + 1:
    #    print("Buffer overfilled, flushing")
    #    CommBuffer.clear()



def waitForReceive():
    global CurrentIP
    global CurrentPort
    global CurrentSocket
    global ReceivedList
    global LastPacketTime
    global AckList
    global IsOpen
    global Ended
    ReceivedList.clear()
    time.sleep(0.1) ###DEBUG !!!!!!!!!!!!!!
    #CurrentSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    #CurrentSocket.bind((CurrentIP, int(CurrentPort)))
    #AckList[4] = False ##DEBUG
    #AckList[3] = False ##DEBUG
    while True:
        if (IsOpen):
            try:
                rec = CurrentSocket.recv(4096)
            except:
                continue
            length = rec[0]*256 + rec[1]
            if length + 10 != len(rec):
                if Verbose: print("Length in header doesn't match packet length")
                LastPacketTime = time.time()
                continue
            header_rest = bytes(rec[2:10])
            unpacked = struct.unpack("!ccHHH",header_rest)
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
                #ReceivedList.append(pkt)
                if pkt.flags == b'\x01':
                    ackKeepAlive = CustomPacket.keepAliveAck()
                    send(ackKeepAlive)
                if pkt.flags == b'\x06':
                    Ended = True
                else:
                    ## check if theres a pending ack with that sequence number
                    #ackIndex = -1
                    #if len(ReceivedList) > 0:
                    ackIndex = (pkt.sequence in AckList.keys() and pkt.sequence_len + 1 == len(AckList))
                    if  ackIndex and pkt.sequence in AckList.keys():
                        AckList[pkt.sequence] = True
            else:
                if Verbose: print("Invalid packet!")
            if Verbose:
                print(f'Header: ', unpacked)
                print(f'Message/Data{int(length)}: ', data)
    return

ShouldRunKeepAlive = False
keepAliveThread: threading.Thread
def startKeepAlive():
    global keepAliveThread
    global ShouldRunKeepAlive
    if (ShouldRunKeepAlive == False):
        keepAliveThread = threading.Thread(target=keepAliveFunction)
        ShouldRunKeepAlive = True
        keepAliveThread.start()

def stopKeepAlive():
    global keepAliveThread
    global ShouldRunKeepAlive
    ShouldRunKeepAlive = False

def keepAliveFunction():
    global CurrentSocket
    global CurrentIP
    global CurrentPort
    global IsOpen
    global ResponseAddress
    global ShouldRunKeepAlive
    global IsBlockingKeepAlive
    IsPrinted = False
    while ShouldRunKeepAlive:
        if IsOpen and ResponseAddress is not None:
            if time.time() - LastPacketTime > 15 and not IsBlockingKeepAlive:
                #CurrentSocket.close()
                if not IsPrinted:
                    print("15s Elapsed in keepalive")
                    IsPrinted = True
                #IsOpen = False
            elif time.time() - LastPacketTime > 2.976:
                CurrentSocket.sendto(CustomPacket.keepAlive(), ResponseAddress)
                IsPrinted = False
                time.sleep(2.95)
            time.sleep(0.05)


def waitForSending():
    global CurrentIP
    global CurrentPort
    global CurrentSocket
    global ResponseAddress
    global MaxPacketSize
    global IsReceiver
    print("Address and port {<address> <port>}:")
    inp = input().split(" ") #ip , port
    CurrentSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    CurrentIP = inp[0]
    CurrentPort = int(inp[1])
    ResponseAddress = (CurrentIP, CurrentPort)
    t = threading.Thread(target=waitForReceive, args=())
    init = False
    inp = input().split(' ')
    if not init:
        t.start()
        init = True
    while inp != "q":
        if inp[0] == "f":
            sendFile(inp[1])
        elif inp[0] == "t":
            sendText(inp[1])
        elif inp[0] == "max":
            MaxPacketSize = int(inp[1])
        elif inp[0] == "s":
            IsReceiver = True
            CurrentSocket.close()
            CurrentSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            waitAsReceiver()
        elif inp[0] == "e":
            endComm()
            CurrentSocket.close()
            CurrentSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        inp = input().split(" ")
    return False

Ended = False

def endComm():
    while not Ended:
        send(CustomPacket.endComm())
        time.sleep(1)

    #<type> <message>
def sendText(text):
    global CurrentSequence
    global MaxPacketSize
    global ReceivedList
    global AckList
    global LastPacketTime
    LastPacketTime = time.time()
    AckList.clear()
    data = []
    acknowledgedAll = False
    textBytes = bytes(text, encoding="UTF-8")
    textLength = len(textBytes)
    if textLength > MaxPacketSize:
        data = [textBytes[i:i + MaxPacketSize] for i in range(0, len(textBytes), MaxPacketSize)]
    else:
        data.append(text.encode())
    print("data: ", data)
    listToSend = []
    #Create packets to be sent and setup acknowledgment list
    if CurrentSequence + len(data) > 65535:
        CurrentSequence = 0
    for x in data:
        listToSend.append(CustomPacket.CustomPacket(len(x), 0, b'\x02', CurrentSequence, len(data)-1, None, x))
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
        if (time.time() - LastPacketTime > 15):
            print("Communication expired after 15s of no response")
            IsOpen = False
            break
        if (unackCount == 0):
            print("All acknowledged")
            if Verbose: print(AckList)
            break
        timeToSleep = 0.2
        if (0.001 * unackCount < timeToSleep):
            timeToSleep = 0.001 * unackCount
        time.sleep(timeToSleep+0.01)
    return


def sendFile(path):
    global CurrentSequence
    global MaxPacketSize
    global ReceivedList
    global AckList
    global LastPacketTime
    f = open(path, "rb")
    binaryFile = list(f.read())
    print(binaryFile)
    f.close()
    LastPacketTime = time.time()
    AckList.clear()
    if CurrentSequence + len(binaryFile) > 65535:
        CurrentSequence = 0
    pathBytes = bytes(path, encoding="utf-8")
    data = []
    acknowledgedAll = False
    fileLength = len(binaryFile)
    binaryFile = bytes(binaryFile)
    if fileLength > MaxPacketSize:
        data += [binaryFile[i:i + MaxPacketSize] for i in range(0, len(binaryFile), MaxPacketSize)]
    else:
        data.append(binaryFile)
    print("data: ", data)
    listToSend = [CustomPacket.CustomPacket(len(pathBytes), b'\x00', b'\x01', CurrentSequence, len(data), None, pathBytes)]
    CurrentSequence += 1
    #Create packets to be sent and setup acknowledgment list
    for x in data:
        listToSend.append(CustomPacket.CustomPacket(len(x), 0, b'\x01', CurrentSequence, len(data), None, x))
        CurrentSequence += 1
    AckList.clear()
    for x in listToSend:
        AckList[x.sequence] = False
    while not acknowledgedAll:
        i = 0
        j = 0
        unackCount = 0
        for x in AckList:
            if not AckList[x]:
                unackCount += 1
                send(listToSend[i].pack())
                j += 1
            i += 1
            if j%20 == 0:
                j += 1
                print(f'Sent: {unackCount}')
                time.sleep(0.01 + (MaxPacketSize / 10000))

        if (time.time() - LastPacketTime > 15):
            print("Communication expired after 15s of no response")
            IsOpen = False
            break
        if (unackCount == 0):
            print("All acknowledged", AckList)
            break
        #timeToSleep = 0.2
        #if (0.001 * unackCount < timeToSleep):
        #    timeToSleep = 0.001 * unackCount
        #time.sleep(timeToSleep+0.01)
        time.sleep(0.5 + (len(AckList) - unackCount) / 1000)
    return
    return


def send(byteData):
    if Verbose:
        print (f"sending {byteData}")
    global CurrentIP
    global CurrentSocket
    global CurrentPort
    global IsOpen
    global ResponseAddress
    global LastPacketTime
    if IsOpen and time.time() - LastPacketTime < 15:
        CurrentSocket.sendto(byteData, ResponseAddress)
    else:
        CurrentSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        CurrentSocket.sendto(byteData, ResponseAddress)
        IsOpen = True
        t = threading.Thread(target=waitForReceive, args=())

if __name__ == '__main__':
    main()

