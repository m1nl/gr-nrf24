#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2024 m1nl.
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

import weakref

import numpy
import pmt
from gnuradio import gr, pdu


class _nrf24_formatter_b(gr.basic_block):
    _preamble_length = 8
    _guard_length = 4

    def __init__(self):
        gr.basic_block.__init__(self, name="nrf24_formatter_b", in_sig=[], out_sig=[])

        self.pdu_in_port_name = "pdu_in"
        self.pdu_out_port_name = "pdu_out"

        self.message_port_register_in(pmt.intern(self.pdu_in_port_name))
        self.message_port_register_out(pmt.intern(self.pdu_out_port_name))

        self.set_msg_handler(pmt.intern(self.pdu_in_port_name), self.process_pdu)

        self.preamble_positive = [1]
        self.preamble_negative = [0]

        for i in range(self._preamble_length - 1):
            self.preamble_positive.append(int(not self.preamble_positive[-1]))
            self.preamble_negative.append(int(not self.preamble_negative[-1]))

        if self.preamble_positive[-1] != 0:
            preamble = self.preamble_negative

            self.preamble_negative = self.preamble_positive
            self.preamble_positive = preamble

    @staticmethod
    def _crc_update(crc, byte, bits=8):
        crc = crc ^ byte << 8

        for x in range(0, bits):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021

            else:
                crc <<= 1

        crc = crc & 0xFFFF
        return crc

    @staticmethod
    def int_to_bits(_byte, bits=8):
        result = list(map(int, bin(_byte).lstrip("0b")))
        result = [0] * (bits - len(result)) + result
        return result

    @staticmethod
    def bytes_to_bits(_bytes):
        return sum([_nrf24_formatter_b.int_to_bits(b, 8) for b in _bytes], [])

    def process_pdu(self, pdu):
        data = pmt.cdr(pdu)
        metadata = pmt.car(pdu)

        if address := pmt.dict_ref(metadata, pmt.intern("address"), None):
            address = pmt.to_python(address)

        if packet_id := pmt.dict_ref(metadata, pmt.intern("packet_id"), None):
            packet_id = pmt.to_python(packet_id)

        if ack := pmt.dict_ref(metadata, pmt.intern("ack"), None):
            ack = pmt.to_python(ack)

        if payload := pmt.dict_ref(metadata, pmt.intern("payload"), None):
            payload = pmt.to_python(payload)

        packet_bits = []

        packet_bits += self.preamble_positive if (address[0] & 0x80) else self.preamble_negative
        packet_bits += _nrf24_formatter_b.bytes_to_bits(address)
        packet_bits += _nrf24_formatter_b.int_to_bits(len(payload), 6)
        packet_bits += _nrf24_formatter_b.int_to_bits(packet_id, 2)
        packet_bits += _nrf24_formatter_b.int_to_bits(ack, 1)
        packet_bits += _nrf24_formatter_b.bytes_to_bits(payload)

        if self._guard_length:
            packet_bits = [int(not (packet_bits[0]))] * self._guard_length + packet_bits

        packet_bytes = bytes(numpy.packbits(packet_bits[self._guard_length + self._preamble_length :]))

        crc = 0xFFFF
        for i in range(0, len(packet_bytes) - 1):
            crc = _nrf24_formatter_b._crc_update(crc, packet_bytes[i])
        crc = _nrf24_formatter_b._crc_update(crc, packet_bytes[len(packet_bytes) - 1], 1)

        packet_bits += _nrf24_formatter_b.int_to_bits(crc, 16)

        pdu = pmt.cons(metadata, pmt.init_u8vector(len(packet_bits), packet_bits))

        self.message_port_pub(pmt.intern(self.pdu_out_port_name), pdu)


class nrf24_encoder_b(gr.hier_block2):
    """
    docstring for block nrf24_encoder_b
    """

    def __init__(self):
        gr.hier_block2.__init__(
            self,
            "nrf24_encoder_b",
            gr.io_signature(0, 0, 0),
            gr.io_signature(1, 1, gr.sizeof_char),
        )

        self.formatter = _nrf24_formatter_b()
        self.pdu_to_stream = pdu.pdu_to_stream_b(pdu.EARLY_BURST_APPEND, 1024)

        self.pdu_port_name = "pdu"
        self.message_port_register_hier_in(self.pdu_port_name)

        self.msg_connect(weakref.proxy(self), self.pdu_port_name, self.formatter, "pdu_in")
        self.msg_connect(self.formatter, "pdu_out", self.pdu_to_stream, "pdus")

        self.connect((self.pdu_to_stream, 0), (weakref.proxy(self), 0))
