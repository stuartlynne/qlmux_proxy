import re

QL_Large = ['NC-11004h', ]
QL_Small = ['NC-16002w', 'NC-18002w', ]


statuses = ['123 PRINTING ', 'BUSY', 'xxx', ]

for status in statuses:
    match status:
        case x if re.match(r'BUSY', x):
            print('BUSY')
        case x if re.match(r'.*PRINTING.*', x):
            print('PRINTING')
        case _:
            print('Unknown')



