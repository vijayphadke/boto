# Copyright (c) 2011 Mitch Garnaat http://garnaat.org/
# Copyright (c) 2011 Amazon.com, Inc. or its affiliates.  All Rights Reserved
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish, dis-
# tribute, sublicense, and/or sell copies of the Software, and to permit
# persons to whom the Software is furnished to do so, subject to the fol-
# lowing conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABIL-
# ITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT
# SHALL THE AUTHOR BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.
#
"""
Some utility functions to deal with mapping Amazon DynamoDB types to
Python types and vice-versa.
"""
import base64
from decimal import (Decimal, Context,
                     Clamped, Overflow, Inexact, Underflow, Rounded)
from exceptions import DynamoDBNumberError


DYNAMODB_CONTEXT = Context(Emin=-128, Emax=126, rounding=None, prec=38,
                           traps=[Clamped, Overflow, Inexact, Rounded, Underflow])


def is_num(n):
    types = (int, long, float, bool, Decimal)
    return isinstance(n, types) or n in types


def is_str(n):
    return isinstance(n, basestring) or (isinstance(n, type) and
                                         issubclass(n, basestring))


def is_binary(n):
    return isinstance(n, Binary)


def serialize_num(s):
    """Cast a number to a string and perform
       validation to ensure no loss of precision.
    """
    try:
        n = str(DYNAMODB_CONTEXT.create_decimal(s))
        if filter(lambda x: x in n, ('Infinity', 'NaN')):
            raise TypeError('Infinity and NaN not supported')
        return n
    except Exception, e:
        msg = '{0} numeric for `{1}`\n{2}'.format(\
            e.__class__.__name__, s, e.message or '')
        raise DynamoDBNumberError(msg)


def convert_num(s):
    return DYNAMODB_CONTEXT.create_decimal(s)


def convert_binary(n):
    return Binary(base64.b64decode(n))


def get_dynamodb_type(val):
    """
    Take a scalar Python value and return a string representing
    the corresponding Amazon DynamoDB type.  If the value passed in is
    not a supported type, raise a TypeError.
    """
    dynamodb_type = None
    if is_num(val):
        dynamodb_type = 'N'
    elif is_str(val):
        dynamodb_type = 'S'
    elif isinstance(val, (set, frozenset)):
        if False not in map(is_num, val):
            dynamodb_type = 'NS'
        elif False not in map(is_str, val):
            dynamodb_type = 'SS'
        elif False not in map(is_binary, val):
            dynamodb_type = 'BS'
    elif isinstance(val, Binary):
        dynamodb_type = 'B'
    if dynamodb_type is None:
        msg = 'Unsupported type "%s" for value "%s"' % (type(val), val)
        raise TypeError(msg)
    return dynamodb_type


def dynamize_value(val):
    """
    Take a scalar Python value and return a dict consisting
    of the Amazon DynamoDB type specification and the value that
    needs to be sent to Amazon DynamoDB.  If the type of the value
    is not supported, raise a TypeError
    """
    dynamodb_type = get_dynamodb_type(val)
    if dynamodb_type == 'N':
        val = {dynamodb_type: serialize_num(val)}
    elif dynamodb_type == 'S':
        val = {dynamodb_type: val}
    elif dynamodb_type == 'NS':
        val = {dynamodb_type: map(serialize_num, val)}
    elif dynamodb_type == 'SS':
        val = {dynamodb_type: [n for n in val]}
    elif dynamodb_type == 'B':
        val = {dynamodb_type: val.encode()}
    elif dynamodb_type == 'BS':
        val = {dynamodb_type: [n.encode() for n in val]}
    return val


class Binary(object):
    def __init__(self, value):
        self.value = value

    def encode(self):
        return base64.b64encode(self.value)

    def __eq__(self, other):
        if isinstance(other, Binary):
            return self.value == other.value
        else:
            return self.value == other

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return 'Binary(%s)' % self.value

    def __str__(self):
        return self.value

    def __hash__(self):
        return hash(self.value)


def item_object_hook(dct):
    """
    A custom object hook for use when decoding JSON item bodys.
    This hook will transform Amazon DynamoDB JSON responses to something
    that maps directly to native Python types.
    """
    if len(dct.keys()) > 1:
        return dct
    if 'S' in dct:
        return dct['S']
    if 'N' in dct:
        return convert_num(dct['N'])
    if 'SS' in dct:
        return set(dct['SS'])
    if 'NS' in dct:
        return set(map(convert_num, dct['NS']))
    if 'B' in dct:
        return convert_binary(dct['B'])
    if 'BS' in dct:
        return set(map(convert_binary, dct['BS']))
    return dct
