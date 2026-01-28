"""
Broadcast SNMP message (IPv4)
+++++++++++++++++++++++++++++

Send SNMP GET request to broadcast address and wait for respons(es):

* with SNMPv2c, community 'public'
* over IPv4/UDP
* to all Agents via broadcast address 255.255.255.255:161
* for OIDs in tuple form

Here we send out a single SNMP request and wait for potentially many SNMP
responses from multiple SNMP Agents listening in local broadcast domain.
Since we can't predict the exact number of Agents responding, this script
just waits for arbitrary time for collecting all responses. This technology
is also known as SNMP-based discovery.

This script performs similar to the following Net-SNMP command:

| $ snmpget -v2c -c public -ObentU 255.255.255.255 1.3.6.1.2.1.1.1.0 1.3.6.1.2.1.1.3.0

"""  #
import sys
from pysnmp.carrier.asyncio.dispatch import AsyncioDispatcher
from pysnmp.carrier.asyncio.dgram import udp
from pyasn1.codec.ber import encoder, decoder
from pysnmp.proto import api

# Broadcast manager settings
maxWaitForResponses = 5
maxNumberResponses = 10

# Protocol version to use
# pMod = api.PROTOCOL_MODULES[api.SNMP_VERSION_1]
pMod = api.PROTOCOL_MODULES[api.SNMP_VERSION_2C]

# Build PDU
reqPDU = pMod.GetRequestPDU()
pMod.apiPDU.set_defaults(reqPDU)
pMod.apiPDU.set_varbinds(
    reqPDU, (
        ("1.3.6.1.2.1.1.1.0", pMod.Null("")), 
        ("1.3.6.1.2.1.1.3.0", pMod.Null("")),
        ("1.3.6.1.4.1.5.0", pMod.Null("")),
     )
)

# Build message
reqMsg = pMod.Message()
pMod.apiMessage.set_defaults(reqMsg)
pMod.apiMessage.set_community(reqMsg, "public")
pMod.apiMessage.set_pdu(reqMsg, reqPDU)


# noinspection PyUnusedLocal,PyUnusedLocal
def __callback(
    transportDispatcher, transportDomain, transportAddress, wholeMsg, reqPDU=reqPDU
):
    print("Received response from %s" % (transportAddress,), file=sys.stderr)
    while wholeMsg:
        rspMsg, wholeMsg = decoder.decode(wholeMsg, asn1Spec=pMod.Message())
        rspPDU = pMod.apiMessage.get_pdu(rspMsg)
        # Match response to request
        if pMod.apiPDU.get_request_id(reqPDU) == pMod.apiPDU.get_request_id(rspPDU):
            # Check for SNMP errors reported
            errorStatus = pMod.apiPDU.get_error_status(rspPDU)
            if errorStatus:
                print(errorStatus.prettyPrint(), file=sys.stderr)
            else:
                for oid, val in pMod.apiPDU.get_varbinds(rspPDU):
                    print(f"{oid.prettyPrint()} = {val.prettyPrint()}", file=sys.stderr)
            transportDispatcher.job_finished(1)
    return wholeMsg


transportDispatcher = AsyncioDispatcher()

transportDispatcher.register_recv_callback(__callback)

# UDP/IPv4
udpSocketTransport = udp.UdpAsyncioTransport().open_client_mode(allow_broadcast=True)
transportDispatcher.register_transport(udp.DOMAIN_NAME, udpSocketTransport)

# Pass message to dispatcher
print("Sending request: %s" % (encoder.encode(reqMsg),), file=sys.stderr)
transportDispatcher.send_message(
    encoder.encode(reqMsg), udp.DOMAIN_NAME, ("255.255.255.255", 161)
    #encoder.encode(reqMsg), udp.DOMAIN_NAME, ("192.168.40.255", 161)
)
print("job started", file=sys.stderr)
# wait for a maximum of 10 responses or time out
transportDispatcher.job_started(1, maxNumberResponses)

print("Run dispatcher", file=sys.stderr)
# Dispatcher will finish as all jobs counter reaches zero
try:
    transportDispatcher.run_dispatcher(maxWaitForResponses)
except:
    raise
finally:
    transportDispatcher.close_dispatcher()
