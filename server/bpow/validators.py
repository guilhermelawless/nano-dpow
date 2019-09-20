import re

from bitstring import BitArray
from hashlib import blake2b

class Validations():

    @classmethod
    def validate_address(cls, address : str) -> bool:
        """Return true if a valid address for currency is found, false otherwise"""
        if address is None:
            return False
        return cls.validate_checksum_xrb(address)

    @classmethod
    def get_banano_address(cls, input_text : str) -> str:
        """Extract a banano address from a string using regex"""
        address_regex = '(?:ban)(?:_)(?:1|3)(?:[13456789abcdefghijkmnopqrstuwxyz]{59})'
        matches = re.findall(address_regex, input_text)
        if len(matches) == 1:
            return matches[0]
        return None

    @classmethod
    def validate_checksum_xrb(cls, address : str) -> bool:
        """Given an xrb/nano/ban address validate the checksum. Return true if valid, false otherwise"""
        if len(address) == 64 and address[:4] == 'ban_':
            # Populate 32-char account index
            account_map = "13456789abcdefghijkmnopqrstuwxyz"
            account_lookup = {}
            for i in range(0, 32):
                account_lookup[account_map[i]] = BitArray(uint=i, length=5)

            # Extract key from address (everything after prefix)
            acrop_key = address[4:-8]
            # Extract checksum from address
            acrop_check = address[-8:]

            # Convert base-32 (5-bit) values to byte string by appending each 5-bit value to the bitstring, essentially bitshifting << 5 and then adding the 5-bit value.
            number_l = BitArray()
            for x in range(0, len(acrop_key)):
                number_l.append(account_lookup[acrop_key[x]])
            number_l = number_l[4:]  # reduce from 260 to 256 bit (upper 4 bits are never used as account is a uint256)

            check_l = BitArray()
            for x in range(0, len(acrop_check)):
                if acrop_check[x] not in account_lookup:
                    return False
                check_l.append(account_lookup[acrop_check[x]])
            check_l.byteswap()  # reverse byte order to match hashing format

            # verify checksum
            h = blake2b(digest_size=5)
            h.update(number_l.bytes)
            return h.hexdigest() == check_l.hex

        return False