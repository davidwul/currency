# Copyright 2023 Compassion Apps (https://compassion.ch)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import itertools
import json
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import timedelta

import dateutil.parser
import logging
_logger = logging.getLogger(__name__)

from odoo import _, fields, models
from odoo.exceptions import UserError



class ResCurrencyRateProviderRiksbank(models.Model):
    _inherit = "res.currency.rate.provider"

    service = fields.Selection(
        selection_add=[("Riksbank", "www.riksbank.se")],
        ondelete={"Riksbank": "set default"},
    )

    def _get_supported_currencies(self):
        return [
            "NOK",
            "SEK",
            "DKK",
            "CHF",
            "EUR",
        ]


    def _obtain_rates(self, base_currency, currencies, date_from, date_to):
        self.ensure_one()
        if self.service != "Riksbank":
            return super()._obtain_rates(
                base_currency, currencies, date_from, date_to
            )  # pragma: no cover
        invert_calculation = False
        if base_currency != "SEK":
            invert_calculation = True
            while 'SEK' in currencies:
                currencies.remove('SEK')
            while base_currency in currencies:
                currencies.remove(base_currency)
            if not currencies:
                currencies.append(base_currency)
            else:
                raise UserError('Cannot retrieve a currency pair that is not compared with SEK ')
        content = defaultdict(dict)

        # NOTE: Step in 10 days is selected to reduce memory impact
        for currency in currencies:
            if currency == 'SEK':
                continue

            url = (
                "https://api-test.riksbank.se/swea/v1/Observations/SEK%(target)sPMI/%(from)s/%(to)s"
            ) % {
                "target": currency,
                "from": str(date_from),
                "to": str(date_to),
            }
            _logger.info("DEBUG retrieving rates at: " + url)
            data = json.loads(self._riksbank_provider_retrieve(url))
            if "error" in data and data["error"]:
                raise UserError(
                    data["error_description"]
                        if "error_description" in data
                        else "Unknown error"
                    )
            for entry in data:
                 content[entry["date"]][currency] = 1/float(entry["value"])

        if invert_calculation:
            for k in content.keys():
                content[k] = {'SEK': 1/content[k][base_currency]}
        return content

    def _riksbank_provider_retrieve(self, url):
        self.ensure_one()

        with self._riksbank_provider_urlopen(url) as response:
            content = response.read().decode('utf-8')
        return content

    def _riksbank_provider_urlopen(self, url):
        self.ensure_one()
        request = urllib.request.Request(url)
        return urllib.request.urlopen(request)
