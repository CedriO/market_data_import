# market_data_import
Manages the external data import jobs into the database. 

Need to manage the database import for;
- External data vendor options data
- yfinance stock data
- Interest rates history (risk free, spot)
- Calendor Events (macro)
- Stocks earning dates 

The jobs import the raw data in raw schemas

Then pgadmin will run the data base jobs to normalize the data

Basic DB Schemas;
- list: indexes the entities and holds a calendar (date series)
- options: 
- rates: SOFR, FED Fund Rate, 90d rate 
- stocks: price, volume, dividends, split
- indexes: 
- catalysts: macro data release, FOMC, major stocks earnings, IPO,   
