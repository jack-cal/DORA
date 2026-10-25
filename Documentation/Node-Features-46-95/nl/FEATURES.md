# SUMUWW · 0.57.46 / 0.6.95

De node biedt kostenopvragen, controle vóór verzending, de status van RBF-vervangingen en gegevens in blokvolgorde. Vervangingen worden gecontroleerd voordat wachtende transacties worden verwijderd. Meervoudige handtekeningen en vergrendelde outputs zijn geïmplementeerd voor afzonderlijke activeringstests; ze zijn nog niet actief op het openbare netwerk.

1 SMW = 100.000.000 yugeon. Automatische kosten bieden drie niveaus op basis van lokale waarnemingen, zonder de bevestigingstijd te garanderen. U kunt een tarief in yugeon/vB invoeren. Controleer vóór verzending de definitieve kosten en het totaal in SMW. Een geweigerde transactie verlaagt het saldo niet.

`1 yugeon = 0.00000001 SMW`

`1 SMW = 100,000,000 yugeon`

Automatische kosten volgen het wachtende datavolume, de blokcapaciteit en de transactieprioriteit. Kosten uit eerdere blokken tellen niet mee. Bij weinig wachtrij blijft het minimumtarief gelden. Het voorbeeld wordt vernieuwd; de definitieve bevestiging legt de kosten vast. De waarneming geldt voor de verbonden lokale node, niet voor alle nodes.

De door dit knooppunt vastgelegde vervangingsgeschiedenis blijft na het herstarten van de wallet bewaard. Verwijderde transacties veranderen het saldo niet.

De verkenner toont onthulde voorwaarden voor meerdere handtekeningen en vergrendelde outputs. Activering op het openbare netwerk is nog niet gepland.


De mininggeschiedenis toont nieuwe uitgifte, transactiekosten en totale beloning per blok afzonderlijk. Het bedrag dat uw wallet ontvangt staat apart. Bij een gedeeltelijk opgeëiste beloning wordt de verdeling niet aangenomen. De node biedt 28 RPC-methoden, waaronder kostenschatting, en controleert en verspreidt ondertekende transacties.
