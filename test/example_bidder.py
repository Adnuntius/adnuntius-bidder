"""Example custom bidder for the Adnuntius platform"""

__copyright__ = "Copyright (c) 2023 Adnuntius AS.  All rights reserved."

from adnbidder.bidder import AdnBidder, BidUpdate
from overrides import override
import argparse


class CustomBidder(AdnBidder):
    """
    Example custom bidder
    """

    def __init__(self, api_key, network_id, api_scheme='https', api_host='api.adnuntius.com'):
        super().__init__(api_key, network_id, api_scheme, api_host)
        self.default_bid = {'currency': 'USD', 'amount': 1}
        self.site_bids = {
            'site_1_id': {'currency': 'USD', 'amount': 2},
            'site_2_id': {'currency': 'USD', 'amount': 3},
            'site_3_id': {'currency': 'USD', 'amount': 4}
        }

    @override
    def get_line_item_bid_updates(self, line_item, line_item_stats):
        """
        This provides a simple fixed bidding strategy, where different bids are
        specified based upon a hard-coded list of bids for each publisher site
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Custom bidder example")
    parser.add_argument('--apiKey', dest='api_key', default='')
    parser.add_argument('--networkId', dest='network_id', default='')
    parser.add_argument('--apiScheme', dest='api_scheme', default='https')
    parser.add_argument('--apiHost', dest='api_host', default='api.adnuntius.com')
    args = parser.parse_args()

    # Initialise the bidder with your API key and network ID
    my_bidder = CustomBidder(args.api_key, args.network_id, api_scheme=args.api_scheme, api_host=args.api_host)

    # This will start the bidder loop, polling for stats and sending bid updates
    my_bidder.start()
