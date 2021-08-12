from easysnmp import snmp_get, snmp_set, snmp_walk

# Grab a single piece of information using an SNMP GET
hostname =  snmp_get('iso.3.6.1.2.1.1.5.0', hostname='ql710w1', community='public', version=1) 
print('value: %s' % hostname.value)

model =  snmp_get('iso.3.6.1.2.1.25.3.2.1.3.1', hostname='ql710w1', community='public', version=1) 
print('value: %s' % model.value)

status =  snmp_get('iso.3.6.1.4.1.11.2.4.3.1.2.0', hostname='ql710w1', community='public', version=1) 
print('value: %s' % status.value)

count =  snmp_get('iso.3.6.1.2.1.43.10.2.1.4.1.1', hostname='ql710w1', community='public', version=1) 
print('count: %s' % count.value)

media =  snmp_get('iso.3.6.1.2.1.43.8.2.1.12.1.1', hostname='ql710w1', community='public', version=1) 
print('media: %s' % media.value)

firmware =  snmp_get('iso.3.6.1.2.1.1.1.0', hostname='ql710w1', community='public', version=1) 
print('media: %s' % firmware.value)

