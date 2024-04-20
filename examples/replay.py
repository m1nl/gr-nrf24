#!/usr/bin/python3

import sys
import time

import pmt
import zmq

context = zmq.Context()

source = context.socket(zmq.SUB)
source.setsockopt(zmq.SUBSCRIBE, b"")
source.connect("tcp://localhost:9120")

sink = context.socket(zmq.PUB)
sink.connect("tcp://localhost:9121")

command = context.socket(zmq.PUB)
command.connect("tcp://localhost:9122")

time.sleep(1)


def set_antenna(antenna: str):
    global command

    cmd = pmt.make_dict()
    cmd = pmt.dict_add(cmd, pmt.intern("antenna"), pmt.intern(antenna))
    command.send(pmt.serialize_str(cmd))


def send_packet(packet: dict):
    global sink

    metadata = pmt.make_dict()
    metadata = pmt.dict_add(
        metadata, pmt.intern("address"), pmt.init_u8vector(len(packet["address"]), list(packet["address"]))
    )
    metadata = pmt.dict_add(metadata, pmt.intern("packet_id"), pmt.from_long(packet["packet_id"]))
    metadata = pmt.dict_add(metadata, pmt.intern("ack"), pmt.from_bool(packet["ack"]))
    metadata = pmt.dict_add(
        metadata, pmt.intern("payload"), pmt.init_u8vector(len(packet["payload"]), list(packet["payload"]))
    )
    pdu = pmt.cons(metadata, pmt.PMT_NIL)
    sink.send(pmt.serialize_str(pdu))


set_antenna("LNAH")
packets = []

while True:
    pdu = pmt.deserialize_str(source.recv())
    data = pmt.cdr(pdu)
    metadata = pmt.car(pdu)

    if packet_id := pmt.dict_ref(metadata, pmt.intern("packet_id"), None):
        packet_id = pmt.to_python(packet_id)

    if ack := pmt.dict_ref(metadata, pmt.intern("ack"), None):
        ack = pmt.to_python(ack)

    if address := pmt.dict_ref(metadata, pmt.intern("address"), None):
        address = list(pmt.to_python(address))

    if payload := pmt.dict_ref(metadata, pmt.intern("payload"), None):
        payload = list(pmt.to_python(payload))

    print(f"[{packet_id}] {address}: {payload}")

    if address[0] == 211 and payload is not None:
        packets.append({"packet_id": packet_id, "address": address, "payload": payload, "ack": ack})

    if len(packets) >= 1000:
        set_antenna("NONE")
        time.sleep(1)
        prev_time = None

        for packet in packets:
            send_packet(packet)
            time.sleep(0.0025)

        packets = []

        time.sleep(1)
        set_antenna("LNAH")
