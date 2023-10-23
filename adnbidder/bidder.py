"""Bidding client for the Adnuntius platform"""

__copyright__ = "Copyright (c) 2023 Adnuntius AS.  All rights reserved."

import signal
import sys
from datetime import datetime, timedelta
from threading import Event
from adnuntius.api import Api
from adnuntius.util import date_to_string, str_to_date


class BidUpdate:
    """
    Object to hold a bid update request
    """
    def __init__(self,
                 line_item_id,
                 site_id=None,
                 ad_unit_id=None,
                 upper_bid_cpm=None,
                 lower_bid_cpm=None,
                 lower_bids_percent=0,
                 pause=None,
                 resume=None):
        """
        Initialise the bid update
        :param line_item_id: line item identifier
        :param site_id: site identifier
        :param upper_bid_cpm: the highest bid to use
        :param lower_bid_cpm: the lowest bid to use
        :param lower_bids_percent: the percentage of bids that should use the low bid amount
        """
        self.line_item_id = line_item_id
        self.site_id = site_id
        self.ad_unit_id = ad_unit_id
        if lower_bid_cpm is None:
            self.lower_bid_cpm = upper_bid_cpm
        else:
            self.lower_bid_cpm = lower_bid_cpm
        self.upper_bid_cpm = upper_bid_cpm
        self.lower_bids_percent = lower_bids_percent
        self.pause = pause
        self.resume = resume

    def to_payload(self) -> dict:
        """
        Converts this object into a dict as expected by the Adnuntius API
        :return:
        """
        if self.pause is not None and self.pause:
            return {
                'id': self.line_item_id,
                'pause': True
            }
        if self.resume is not None and self.resume:
            return {
                'id': self.line_item_id,
                'resume': True
            }
        payload = {
            'id': self.line_item_id,
            'lowerCpm': self.lower_bid_cpm,
            'upperCpm': self.upper_bid_cpm,
            'lowBidPercent': self.lower_bids_percent,
        }
        if self.ad_unit_id is not None:
            payload['adUnit'] = self.ad_unit_id
        elif self.site_id is not None:
            payload['site'] = self.site_id
        return payload


class AdnBidder:
    """
    The main bidder class.
    Custom bidders should inherit from this base, and override methods to provide custom
    bidding algorithms.
    """

    def __init__(self, api_key, network_id, api_scheme='https', api_host='api.adnuntius.com'):
        """
        Initialises a new bidder.
        :param api_key: Your API key
        :param network_id: The network identifier for your Adnuntius account
        :param api_scheme: https or http
        :param api_host: Hostname for Adnuntius API server
        """
        api_location = api_scheme + '://' + api_host + '/api'
        self.api_client = Api(None, None, api_location, api_key=api_key)
        self.api_client.defaultArgs['context'] = network_id
        self.loop_period = timedelta(minutes=5)
        self.exit = None

    def start(self):
        """
        Starts the bidding service.
        This runs the main service loop, which periodically fetches the current bidding data for
        each active line-item and makes adjustments to the bid prices as required.
        """
        print('Bidder started!')
        self.exit = Event()

        for sig in ('TERM', 'HUP', 'INT'):
            signal.signal(getattr(signal, 'SIG' + sig), self.shutdown)

        while not self.exit.is_set():
            self.update_all_bids()
            self.call_back()
            self.exit.wait(self.loop_period.total_seconds())
        sys.exit(0)

    def update_all_bids(self):
        """
        Updates the bids for all active Adnuntius line-items.
        This method is a good entry point if the bidder is being run according to an externally
        controlled schedule, for example as a scheduled AWS Lambda.
        - Queries for all active line-items configured for custom bidding control
        - Adjusts the bidding, if required, for each line-item
        :return:
        """
        query_filter = {
            'where': 'biddingAlgorithm=CUSTOM;userState in APPROVED;'
                     'objectState=ACTIVE;executionState in RUNNING,READY '
        }
        line_items = self.api_client.line_items.query(args=query_filter)
        if len(line_items['results']) == 0:
            print('No custom bidding line-items found')
        else:
            for line_item in line_items['results']:
                print('Updating bids for line-item "' + line_item['name'] + '"')
                self.update_line_item_bids(line_item)
                print('Done!')

    def update_line_item_bids(self, line_item):
        """
        Updates the bids for a single Adnuntius line-item.
        - Fetches the bidding stats (win-rates, average win/lose CPM, etc)
        - Gets the required updates based upon the bidding stats
        - Sends the updates to Adnuntius
        :param line_item: An Adnuntius line-item or line-item identifier
        :return:
        """
        if not (isinstance(line_item, dict) and 'id' in line_item):
            line_item_id = line_item
            line_item = self.api_client.line_items.get(line_item_id)
        line_item_stats = LineItemBidStats(self.api_client, line_item)
        for bid_update in self.get_line_item_bid_updates(line_item, line_item_stats):
            try:
                self.api_client.bidding.update(bid_update.to_payload())
            except RuntimeError as err:
                self.bid_error_handler(err)

    def get_line_item_bid_updates(self, line_item, line_item_stats):
        """
        This is the heart of the bidding control algorithm. Custom bidder implementations
        should override this method to provide custom bidding decisions in their adaptor.
        :param line_item: The Line Item object
        :param line_item_stats: The bid data for the Line Item across all the Sites where it runs.
        :return: A list of Bid Updates to adjust the bid CPM for the Line Item on specific Sites.
        """
        budget = line_item['objectives']['BUDGET']['amount']
        if 'spendDelivery' in line_item:
            spent_budget = line_item['spendDelivery']['amount']
        else:
            spent_budget = 0
        remaining_budget = budget - spent_budget
        if remaining_budget <= 0:
            return []
        end = str_to_date(line_item['endDate']).replace(tzinfo=None)
        now = datetime.utcnow()
        remaining_minutes = (end - now).total_seconds() / 60
        required_spend_per_minute = remaining_budget / remaining_minutes
        bid_updates = []
        for site_bid in line_item_stats.site_bids:
            bid_lower = True
            if site_bid.bid_rate > 0.9:
                # Bidding a lot, so probably under delivering
                if site_bid.win_rate < 0.95:
                    # Try bidding higher
                    bid_lower = False
            site_impressions_per_minute = site_bid.impression_share * \
                                          line_item_stats.available_impressions_per_second * 60
            site_required_spend_per_minute = site_bid.impression_share * required_spend_per_minute
            for bid in site_bid.advertiser_site_bids.bid_win_rates:
                if bid_lower or bid.bid_cpm['amount'] > site_bid.average_winning_cpm['amount']:
                    expected_spend_per_minute = bid.bid_cpm['amount'] * bid.win_rate * \
                                                site_impressions_per_minute / 1000
                    if expected_spend_per_minute > site_required_spend_per_minute:
                        bid_update = BidUpdate(line_item_stats.line_item_id,
                                               site_bid.site_id,
                                               bid.bid_cpm)
                        bid_updates.append(bid_update)
                        break
        return bid_updates

    def shutdown(self, sig=None, frame=None):
        """
        Shuts down the bidder immediately
        :param sig:
        :param frame:
        :return:
        """
        if self.exit is not None:
            print('Shutting down bidder...')
            self.exit.set()

    def call_back(self):
        """
        A method stub that can be overridden by child classes.
        This method will be called once per cycle in the main service loop.
        :return:
        """
        return self

    def bid_error_handler(self, error):
        """
        This method will be called if there is an error sending a bid update.
        Should be overriden by custom bidders if you don't want to shut down on any error.
        :return:
        """
        print(error)
        self.shutdown()


class BidWinRate:
    """
    Structure for holding a bid CPM and observed win rate.
    """
    def __init__(self, bid_win_rate):
        self.bid_cpm = bid_win_rate['bidCpm']
        self.win_rate = bid_win_rate['winRate']

    def __str__(self):
        return str(self.bid_cpm['amount']) + ' ' + str(self.win_rate)


class AdvertiserSiteBids:
    """
    Structure for holding the historical win rate, at each CPM price, for an Advertiser on a
    specific Site. This pools data from ALL the Advertiser's line-items.
    - An entry is provided for any CPM bid used in the last 24 hours.
    - At each CPM price, only the most recent 1 hour of bids at that price is used to estimate the
      expected win rate.
    - The win rate is expressed as a number from 0 to 1, where 0 means the bid always loses and 1
      means it always wins.
    """
    def __init__(self, api_client, advertiser_id, site_id):
        """
        Initialise the object
        :param api_client: An initialised Adnuntius API client
        :param advertiser_id: The identifier for the Line Item's Advertiser
        :param site_id: The identifier for the Site
        """
        advertiser_site_bid = api_client.bidding_advertiser_site_stats.get([advertiser_id, site_id])
        self.advertiser_name = advertiser_site_bid['advertiser']['name']
        self.advertiser_id = advertiser_site_bid['advertiser']['id']
        self.site_name = advertiser_site_bid['site']['name']
        self.site_id = advertiser_site_bid['site']['id']
        self.bid_win_rates = [BidWinRate(bwr) for bwr in advertiser_site_bid['bids']]


class SiteBidStats:
    """
    Structure for holding bidding data for a Line Item on a specific Site.
    Includes:
    - The total available impressions to bid on during the analysed time-period.
    - The impression share for this Site, expressed as a number from 0 to 1, relative to the
      total impressions available to the Line Item across ALL sites.
    - The win rate, expressed as a number from 0 to 1. A value of 1 means that the Line Item wins
      every time that it submits a bid. A value of 0 means that it never wins.
    - The bidding rate, expressed as a number from 0 to 1. A value lower than 1 means that the
      line-item delivery is being rate controlled by the system and is therefore not bidding on
      every impression.
    - The average winning bid CPM.
    - The average losing bid CPM.
    - The pooled Advertiser bidding stats for this Site. See
    """
    def __init__(self, api_client, advertiser_id, line_item_site_bids):
        """
        Initialise the object
        :param api_client: An initialised Adnuntius API client
        :param advertiser_id: The identifier for the Line Item's Advertiser
        :param line_item_site_bids: The bidding data from the Adnuntius API.
        """
        self.site_name = line_item_site_bids['site']['name']
        self.site_id = line_item_site_bids['site']['id']
        self.available_impressions = line_item_site_bids['availableImpressions']
        self.impression_share = line_item_site_bids['trafficShare']
        self.bid_rate = line_item_site_bids['bidRate']
        self.win_rate = line_item_site_bids['winRate']
        self.average_winning_cpm = line_item_site_bids['averageWinningCpm']
        self.average_losing_cpm = line_item_site_bids['averageLosingCpm']
        self.advertiser_site_bids = AdvertiserSiteBids(api_client, advertiser_id, self.site_id)


class LineItemBidStats:
    """
    Structure for holding the bidding data for a Line Item.
    Includes:
    - The total available impressions to bid on during the analysed time period (default: the last
      one hour).
    - The available impressions per second.
    - The bidding data broken down by each Site that the line-item has bid on during the analysed
      time period.
    """
    def __init__(self, api_client, line_item, window=timedelta(hours=1)):
        """
        Initialise the object
        :param api_client: An initialised Adnuntius API client
        :param line_item_id: The identifier for the Line Item
        :param window: The time window to analyse. Default is one hour.
        """
        self.line_item_id = line_item['id']
        self.line_item_name = line_item['name']
        since = datetime.utcnow() - window
        line_item_stats = api_client.bidding_line_item_stats.get(self.line_item_id,
                                                                 {'since': date_to_string(since)})
        self.advertiser_name = line_item_stats['advertiser']['name']
        self.advertiser_id = line_item_stats['advertiser']['id']
        self.available_impressions = line_item_stats['availableImpressions']
        range_seconds = line_item_stats['timeRangeSeconds']
        if range_seconds > 0:
            self.available_impressions_per_second = self.available_impressions / range_seconds
        else:
            self.available_impressions_per_second = 0
        self.site_bids = [SiteBidStats(api_client, self.advertiser_id, site_bid)
                          for site_bid in line_item_stats['siteBids']]
