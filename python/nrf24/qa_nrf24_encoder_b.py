#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2024 m1nl.
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
import os
import time

import pmt
from gnuradio import blocks, gr, gr_unittest
from gnuradio.nrf24 import nrf24_encoder_b


class qa_nrf24_encoder_b(gr_unittest.TestCase):
    def setUp(self):
        self.tb = gr.top_block()

        self.encoder = nrf24_encoder_b()
        self.vs = blocks.vector_sink_b(1)
        self.tag_debug = blocks.tag_debug(gr.sizeof_char * 1, "", "")
        self.tag_debug.set_display(True)

    def tearDown(self):
        self.tb = None

    def test_001_descriptive_test_name(self):
        metadata = pmt.make_dict()
        metadata = pmt.dict_add(metadata, pmt.intern("address"), pmt.init_u8vector(5, [1, 2, 3, 4, 5]))
        metadata = pmt.dict_add(metadata, pmt.intern("packet_id"), pmt.from_long(1))
        metadata = pmt.dict_add(metadata, pmt.intern("ack"), pmt.from_bool(False))

        payload = [1, 2, 3, 4, 5]

        payload = pmt.init_u8vector(len(payload), payload)
        metadata = pmt.dict_add(metadata, pmt.intern("payload"), payload)

        in_pdu = pmt.cons(metadata, pmt.PMT_NIL)
        strobe = blocks.message_strobe(in_pdu, 600)

        self.tb.connect((self.encoder, 0), (self.vs, 0))
        self.tb.connect((self.encoder, 0), (self.tag_debug, 0))

        self.tb.msg_connect(strobe, pmt.intern("strobe"), self.encoder, pmt.intern("pdu"))
        self.tb.start()

        time.sleep(1)

        self.tb.stop()
        self.tb.wait()

        print("".join(map(str, self.vs.data())))


if __name__ == "__main__":
    gr_unittest.run(qa_nrf24_encoder_b)
