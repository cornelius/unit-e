#!/usr/bin/env python3
# Copyright (c) 2018-2019 The Unit-e developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.

from decimal import Decimal
from enum import Enum
from test_framework.messages import ser_compact_size
import codecs

class AdminCommandType(Enum):
    ADD_TO_WHITELIST = 0,
    REMOVE_FROM_WHITELIST = 1
    RESET_ADMINS = 2
    END_PERMISSIONING = 3


def compact_size_to_str(size):
    str_bytes = codecs.encode(ser_compact_size(size), 'hex')
    return str(str_bytes, 'utf-8')


class Admin:
    @staticmethod
    def create_raw_command(command_type: AdminCommandType, payload=None):
        result_string = "%02d" % command_type.value

        if payload is None:
            return result_string + "00"

        payload_len = len(payload)

        result_string += compact_size_to_str(payload_len)

        for p in payload:
            bytes_in_payload = len(p) // 2
            result_string += compact_size_to_str(bytes_in_payload)
            result_string += p

        return result_string

    @staticmethod
    def import_admin_keys(node):
        private_keys = ["cQzPd94MUUE6Gtoue6Y86S7apaLwJA223f4Md3GiaX7j7vGDPDXp",
                        "cVYxRyHk6B9x3pgnUz1vEkvVpNhCiCvtTbYDLy4EzW8PNKRyHNvG",
                        "cRFymdYKDZpDEkZLeR4WNbk7hiZtnG3nuWH4uyxwtKyJdT54vf9b"]

        for key in private_keys:
            node.importprivkey(key)

        addresses = ["n1Rf25dBYJ2PAMUx5FbAWmRVHt1CkAS6Vj",
                     "mwEynwmJ2XEQ6sm2U7ji7yLaEUhbkRCZx2",
                     "mjqD9Fc81DjCgNfJqLkvrXUVYqygCxhabm"]

        return addresses

    @staticmethod
    def authorize(framework, admin_node, donor_node=None,
                  amount=Decimal("10")):
        addresses = Admin.import_admin_keys(admin_node)

        address = admin_node.addmultisigaddress(2, addresses, "",
                                                "p2sh-segwit")["address"]

        if donor_node is None:
            donor_node = admin_node

        return Admin(framework, admin_node, donor_node, address, amount)

    def send(self, commands, fee=Decimal("0.001")):
        self.last_exception = None

        if self.prevout is None:
            raise AssertionError("No prevout")

        txid = self.admin_node.sendadmincommands([self.prevout], fee,
                                                 commands, self.address)
        self.framework.wait_for_transaction(txid)
        self.prevout = Admin.find_output_for_address(self.admin_node, txid,
                                                     self.address)
        self.framework.generate_sync(self.donor_node)
        return txid

    @staticmethod
    def find_output_for_address(node, txid, address):
        raw_tx = node.getrawtransaction(txid)
        tx = node.decoderawtransaction(raw_tx)

        for out in tx["vout"]:
            script_pub_key = out["scriptPubKey"]
            addresses = script_pub_key.get("addresses", None)
            if addresses is None:
                continue

            if address in addresses:
                return txid, out["n"]

        return None

    def __init__(self, framework, admin_node, donor_node, address, amount):
        super().__init__()

        if donor_node is None:
            donor_node = admin_node

        self.admin_node = admin_node
        self.donor_node = donor_node
        self.address = address
        self.framework = framework

        self.prevout = None
        self.last_exception = None

        txid = donor_node.sendtoaddress(address, amount)
        framework.wait_for_transaction(txid)

        self.prevout = Admin.find_output_for_address(self.admin_node, txid,
                                                     self.address)

    def whitelist(self, pubkeys):
        command = {
            "cmd": "ADD_TO_WHITELIST",
            "payload": pubkeys
        }
        return self.send([command])

    def blacklist(self, pubkeys):
        command = {
            "cmd": "REMOVE_FROM_WHITELIST",
            "payload": pubkeys
        }
        return self.send([command])

    def end_permissioning(self):
        return self.send([{'cmd': 'END_PERMISSIONING'}])
