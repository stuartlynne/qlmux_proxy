from easysnmp import snmp_get, snmp_set, snmp_walk

# Grab a single piece of information using an SNMP GET
status =  snmp_get('iso.3.6.1.4.1.11.2.4.3.1.2.0', hostname='ql710w1', community='public', version=1) 
print('value: %s' % status.value)

count =  snmp_get('iso.3.6.1.2.1.43.10.2.1.4.1.1', hostname='ql710w1', community='public', version=1) 
print('count: %s' % count.value)

