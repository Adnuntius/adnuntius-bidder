"""Example custom bidder for the Adnuntius platform"""

__copyright__ = "Copyright (c) 2023 Adnuntius AS.  All rights reserved."

import sys

from adnbidder.bidder import AdnBidder, BidUpdate
from overrides import override
import argparse
import datetime


class FixedPriceBidder(AdnBidder):
    """
    Example custom bidder that provides a simple fixed bidding strategy, where different bids are
    specified based upon a hard-coded list of bids for each publisher site
    """

    def __init__(self, api_key, network_id, site_bids=None, api_scheme='https', api_host='api.adnuntius.com'):
        super().__init__(api_key, network_id, api_scheme, api_host)
        self.default_bid = {'currency': 'USD', 'amount': 1}
        if site_bids is None:
            self.site_bids = {
                'site_1_id': {'currency': 'USD', 'amount': 2},
                'site_2_id': {'currency': 'USD', 'amount': 3},
                'site_3_id': {'currency': 'USD', 'amount': 4}
            }
        else:
            self.site_bids = site_bids

    @override
    def get_line_item_bid_updates(self, line_item, line_item_stats):
        """
        """
        bid_updates = []
        for site_bid in line_item_stats.site_bids:
            print('Site: ' + site_bid.site_name)
            if site_bid.site_id in self.site_bids:
                bid_amount = self.site_bids[site_bid.site_id]
            else:
                bid_amount = self.default_bid
            update = BidUpdate(line_item_stats.line_item_id, site_bid.site_id, bid_amount)
            bid_updates.append(update)
        return bid_updates

    @override
    def bid_error_handler(self, error):
        """
        Just log errors and keep running.
        """
        print(error)


class PausingBidder(AdnBidder):
    """
    Example custom bidder that pauses line-items for a fixed time each day
    """

    def __init__(self, api_key, network_id, pause_start=None, pause_end=None, time_zone=None, api_scheme='https', api_host='api.adnuntius.com'):
        super().__init__(api_key, network_id, api_scheme, api_host)
        if pause_start is None:
            self.pause_start = datetime.time(21, 0)
        else:
            self.pause_start = pause_start
        if pause_end is None:
            self.pause_end = datetime.time(5, 0)
        else:
            self.pause_end = pause_end
        if time_zone is None:
            # Defaulting to a time zone offset of UTC + 1 hour
            self.time_zone = datetime.timezone(datetime.timedelta(hours=1))
        else:
            self.time_zone = time_zone

    @override
    def get_line_item_bid_updates(self, line_item, line_item_stats):
        bid_updates = []
        current_time = datetime.datetime.now(self.time_zone).time()
        if self.pause_start < current_time < self.pause_end:
            print('Line item ' + line_item['name'] + ' is paused')
            update = BidUpdate(line_item_stats.line_item_id, pause=True)
        else:
            print('Line item ' + line_item['name'] + ' is running')
            update = BidUpdate(line_item_stats.line_item_id, resume=True)
        bid_updates.append(update)
        return bid_updates


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Custom bidder example")
    parser.add_argument('--apiKey', dest='api_key', default='')
    parser.add_argument('--networkId', dest='network_id', default='')
    parser.add_argument('--apiScheme', dest='api_scheme', default='https')
    parser.add_argument('--apiHost', dest='api_host', default='api.adnuntius.com')
    parser.add_argument('--bidderType', dest='bidder_type', default='FIXED_PRICE')
    args = parser.parse_args()

    if args.bidder_type == 'FIXED_PRICE':
        my_bidder = FixedPriceBidder(args.api_key, args.network_id, api_scheme=args.api_scheme, api_host=args.api_host)
    elif args.bidder_type == 'PAUSING':
        my_bidder = PausingBidder(args.api_key, args.network_id, api_scheme=args.api_scheme, api_host=args.api_host)
    else:
        print("Invalid bidder type: " + args.bidder_type)
        sys.exit()

    # This will start the bidder loop, polling for stats and sending bid updates
    my_bidder.start()
