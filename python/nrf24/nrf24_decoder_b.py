#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2024 m1nl.
#
# SPDX-License-Identifier: GPL-3.0-or-later
#


import time
from enum import Enum

import numpy
import pmt
from gnuradio import gr


class nrf24_decoder_fsm_state(Enum):
    INIT = 0
    PREAMBLE_DETECT = 1
    READ_ADDRESS_BEGIN = 2
    READ_ADDRESS_CONTINUE = 3
    READ_PCF = 4
    READ_PAYLOAD = 5
    READ_CRC = 6
    DONE = 7


class nrf24_decoder_b(gr.sync_block):
    """
    docstring for block nrf24_decoder_b
    """

    _preamble_size_bits = 8
    _pcf_size_bits = 9

    _maximum_address_size_bytes = 5
    _maximum_payload_size_bytes = 32
    _maximum_crc_size_bytes = 2

    _maximum_packet_size_bits = (
        _preamble_size_bits + (_maximum_address_size_bytes + _maximum_payload_size_bytes + _maximum_crc_size_bytes) * 8
    ) * 10

    def __init__(self, address_size=5, crc_size=2):
        gr.sync_block.__init__(
            self,
            name="nrf24_decoder_b",
            in_sig=[
                numpy.byte,
            ],
            out_sig=[],
        )

        self.address_size = address_size
        self.crc_size = crc_size

        self.address_size_bits = address_size * 8
        self.crc_size_bits = crc_size * 8

        self.state = nrf24_decoder_fsm_state.INIT
        self.buffer = numpy.arange(nrf24_decoder_b._maximum_packet_size_bits)

        self.head = nrf24_decoder_b._maximum_packet_size_bits
        self.position = 0

        self.address = None
        self.payload_len = 0
        self.packet_id = 0
        self.ack = False
        self.payload = None
        self.crc = None

        self.pdu_port_name = "pdu"
        self.message_port_register_out(pmt.intern(self.pdu_port_name))

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

    def work(self, input_items, output_items):
        shift = min(self.head, len(self.buffer))

        in0 = input_items[0][:shift]
        shift = len(in0)

        self.buffer = numpy.roll(self.buffer, -shift)
        self.buffer[-shift:] = in0
        self.head -= shift

        index = self.head + self.position

        while index < len(self.buffer):
            symbol = self.buffer[index]

            # print(
            #    f"index={index} position={self.position} head={self.head} state={self.state} symbol={symbol} nitems_read={self.nitems_read(0)}"
            # )

            if self.state == nrf24_decoder_fsm_state.INIT:
                self.state = nrf24_decoder_fsm_state.PREAMBLE_DETECT
                self.position += 1

            elif self.state == nrf24_decoder_fsm_state.PREAMBLE_DETECT:
                if self.buffer[index - 1] != symbol:
                    if self.position == nrf24_decoder_b._preamble_size_bits - 1:
                        self.state = nrf24_decoder_fsm_state.READ_ADDRESS_BEGIN

                    self.position += 1

                else:
                    self.state = nrf24_decoder_fsm_state.INIT
                    self.head += 1
                    self.position = 0

            elif self.state == nrf24_decoder_fsm_state.READ_ADDRESS_BEGIN:
                if self.buffer[index - 1] != symbol:
                    self.state = nrf24_decoder_fsm_state.READ_ADDRESS_CONTINUE
                    self.position += 1

                else:
                    self.state = nrf24_decoder_fsm_state.INIT
                    self.head += 1
                    self.position = 0

            elif self.state == nrf24_decoder_fsm_state.READ_ADDRESS_CONTINUE:
                if self.position == self.address_size_bits + nrf24_decoder_b._preamble_size_bits - 1:
                    self.address = bytes(numpy.packbits(self.buffer[index - self.address_size_bits + 1 : index + 1]))

                    self.state = nrf24_decoder_fsm_state.READ_PCF

                self.position += 1

            elif self.state == nrf24_decoder_fsm_state.READ_PCF:
                if (
                    self.position
                    == nrf24_decoder_b._pcf_size_bits + self.address_size_bits + nrf24_decoder_b._preamble_size_bits - 1
                ):
                    pcf_bits = self.buffer[index - nrf24_decoder_b._pcf_size_bits + 1 : index + 1]

                    self.payload_len = int(numpy.packbits(numpy.append([0] * 2, pcf_bits[0:6]))[0])
                    self.packet_id = int(numpy.packbits(numpy.append([0] * 6, pcf_bits[6:8]))[0])
                    self.ack = pcf_bits[8] == 1

                    self.payload = None
                    self.crc = None

                    if self.payload_len == 0:
                        self.state = nrf24_decoder_fsm_state.READ_CRC

                    elif self.payload_len <= nrf24_decoder_b._maximum_payload_size_bytes:
                        self.state = nrf24_decoder_fsm_state.READ_PAYLOAD

                    else:
                        self.state = nrf24_decoder_fsm_state.INIT
                        self.head += 1
                        self.position = -1

                self.position += 1

            elif self.state == nrf24_decoder_fsm_state.READ_PAYLOAD:
                if (
                    self.position
                    == self.payload_len * 8
                    + nrf24_decoder_b._pcf_size_bits
                    + self.address_size_bits
                    + nrf24_decoder_b._preamble_size_bits
                    - 1
                ):
                    self.payload = bytes(numpy.packbits(self.buffer[index + 1 - self.payload_len * 8 : index + 1]))

                    self.state = nrf24_decoder_fsm_state.READ_CRC

                self.position += 1

            elif self.state == nrf24_decoder_fsm_state.READ_CRC:
                if (
                    self.position
                    == self.crc_size_bits
                    + self.payload_len * 8
                    + nrf24_decoder_b._pcf_size_bits
                    + self.address_size_bits
                    + nrf24_decoder_b._preamble_size_bits
                    - 1
                ):
                    self.crc = int.from_bytes(
                        bytes(numpy.packbits(self.buffer[index - self.crc_size_bits + 1 : index + 1])),
                        "big",
                    )

                    self.state = nrf24_decoder_fsm_state.DONE

                self.position += 1

            if self.state == nrf24_decoder_fsm_state.DONE:
                a = (
                    index
                    - self.crc_size_bits
                    - self.payload_len * 8
                    - nrf24_decoder_b._pcf_size_bits
                    - self.address_size_bits
                    + 1
                )
                b = index - self.crc_size_bits + 1

                packet_bytes = bytes(
                    numpy.packbits(
                        self.buffer[
                            index
                            - self.crc_size_bits
                            - self.payload_len * 8
                            - nrf24_decoder_b._pcf_size_bits
                            - self.address_size_bits
                            + 1 : index
                            - self.crc_size_bits
                            + 1,
                        ]
                    )
                )

                crc = 0xFFFF
                for i in range(0, len(packet_bytes) - 1):
                    crc = self._crc_update(crc, packet_bytes[i])
                crc = self._crc_update(crc, packet_bytes[len(packet_bytes) - 1], 1)

                if crc != self.crc:
                    self.state = nrf24_decoder_fsm_state.INIT
                    self.head += 1
                    self.position = 0

                else:
                    metadata = pmt.make_dict()

                    metadata = pmt.dict_add(metadata, pmt.intern("time"), pmt.from_long(round(time.monotonic() * 1000)))
                    metadata = pmt.dict_add(
                        metadata, pmt.intern("address"), pmt.init_u8vector(self.address_size, list(self.address))
                    )
                    metadata = pmt.dict_add(metadata, pmt.intern("payload_len"), pmt.from_long(self.payload_len))
                    metadata = pmt.dict_add(metadata, pmt.intern("packet_id"), pmt.from_long(self.packet_id))
                    metadata = pmt.dict_add(metadata, pmt.intern("ack"), pmt.from_bool(self.ack))

                    if self.payload:
                        payload = pmt.init_u8vector(self.payload_len, list(self.payload))
                        metadata = pmt.dict_add(metadata, pmt.intern("payload"), payload)

                    if self.crc:
                        metadata = pmt.dict_add(metadata, pmt.intern("crc"), pmt.from_long(self.crc))

                    pdu = pmt.cons(metadata, pmt.init_u8vector(len(packet_bytes), list(packet_bytes)))
                    self.message_port_pub(pmt.intern(self.pdu_port_name), pdu)

                    self.state = nrf24_decoder_fsm_state.INIT
                    self.head += self.position
                    self.position = 0

            index = self.head + self.position

        return len(in0)
