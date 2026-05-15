# Supported Bank Statement Column Names

The universal parser recognizes the following column headers from bank statements worldwide.

## Date Columns
- `date`, `transaction date`, `trans date`, `posting date`, `posted`
- `value date`, `txn date`, `created`, `time`, `completed`, `settled`
- `booked`, `effective date`, `process date`, `entry date`, `booking date`
- **German:** `datum`, `buchungstag`, `wertstellung`
- **French:** `date opération`, `date valeur`
- **Spanish:** `fecha`, `fecha valor`

## Debit/Withdrawal Columns (Money OUT)
- `withdrawn`, `withdrawals`, `withdrawal`
- `paid out`, `paidout`, `paid_out`
- `money out`, `moneyout`, `money_out`
- `debit`, `debits`, `dr`
- `out`, `outgoing`, `outgoings`
- `payments out`, `payment out`
- `expenditure`, `spend`, `spent`
- `charges`, `charge`
- **With currency:** `withdrawn(£)`, `withdrawn (£)`, `debit(£)`, `out(£)`, etc.
- **German:** `ausgaben`, `abbuchung`, `soll`
- **French:** `débit`, `dépenses`, `sortie`
- **Spanish:** `débito`, `cargo`, `salida`
- **Italian:** `uscita`, `addebito`

## Credit/Deposit Columns (Money IN)
- `paid in`, `paidin`, `paid_in`
- `money in`, `moneyin`, `money_in`
- `credit`, `credits`, `cr`
- `in`, `incoming`, `incomings`
- `receipts`, `receipt`
- `deposits`, `deposit`, `deposited`
- `income`, `received`
- `payments in`, `payment in`
- **With currency:** `paid in(£)`, `credit(£)`, `in(£)`, `deposits(£)`, etc.
- **German:** `einnahmen`, `gutschrift`, `haben`
- **French:** `crédit`, `entrée`, `recettes`
- **Spanish:** `crédito`, `abono`, `entrada`
- **Italian:** `entrata`, `accredito`

## Amount Columns (Single column, direction from sign)
- `amount`, `value`, `sum`, `total`
- `transaction amount`, `txn amount`, `balance change`
- **With currency:** `amount(£)`, `value(£)`, etc.
- **German:** `betrag`, `umsatz`, `summe`
- **French:** `montant`
- **Spanish:** `importe`, `monto`

## Description Columns
- `description`, `details`, `narrative`, `particulars`, `reference`
- `memo`, `notes`, `transaction`, `type`
- `merchant`, `payee`, `name`, `beneficiary`
- `counter party`, `counterparty`, `remitter`
- `transaction details`, `payment details`
- **German:** `verwendungszweck`, `buchungstext`, `empfänger`
- **French:** `libellé`, `motif`, `bénéficiaire`
- **Spanish:** `concepto`, `descripción`, `beneficiario`

## Balance Columns
- `balance`, `running balance`, `available balance`
- `account balance`, `closing balance`, `bal`
- `cumulative`, `running total`
- **With currency:** `balance(£)`, etc.
- **German/Spanish:** `saldo`, `kontostand`
- **French:** `solde`

---

## Supported Banks (Tested)
- NatWest / RBS
- Barclays
- HSBC
- Lloyds
- Santander
- Nationwide
- Halifax
- Monzo
- Starling
- Revolut
- Chase UK
- American Express

## Adding Support for New Banks
If a bank uses column names not in this list, add them to:
1. `backend/app/services/natwest_statement_parser.py` - `_find_header_and_columns()`
2. `backend/app/services/enhanced_universal_parser.py` - `__init__()` column name lists
