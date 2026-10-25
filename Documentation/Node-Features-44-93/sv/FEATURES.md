# SUMUWW · 0.57.44 / 0.6.93

Noden lägger till avgiftsfrågor, kontroll före sändning, status för RBF-ersättning och data i blockordning. Ersättningen valideras innan väntande transaktioner tas bort. Flera signaturer och låsta utdata är implementerade för isolerade aktiveringstester; de är ännu inte aktiva i det offentliga nätverket.

1 SMW = 100 000 000 yugeon. Automatiska avgifter erbjuder tre nivåer utifrån lokala observationer, utan att garantera bekräftelsetiden. Du kan ange en sats i yugeon/vB. Kontrollera den slutliga avgiften och totalsumman i SMW innan du skickar. En avvisad transaktion minskar inte saldot.

`1 yugeon = 0.00000001 SMW`

`1 SMW = 100,000,000 yugeon`

Automatiska avgifter utgår från väntande datamängd, blockkapacitet och transaktionsprioritet. Avgifter i tidigare block används inte. Vid kort kö gäller minimiavgiften. Förhandsvisningen uppdateras; den slutliga bekräftelsen låser avgiften. Uppgifterna gäller den anslutna lokala noden, inte alla noder.
