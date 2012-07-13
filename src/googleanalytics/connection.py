from googleanalytics.exception import GoogleAnalyticsClientError
from googleanalytics import config
from googleanalytics.account import Account
from xml.etree import ElementTree

import re
import urllib
import urllib2

DEBUG = False
PRETTYPRINT = True
TIMEOUT = 10

class GAConnection:
    user_agent = 'python-gapi-v2'
    auth_token = None

    def __init__(self, google_email=None, google_password=None):
        authtoken_pat = re.compile(r"Auth=(.*)")
        base_url = 'https://www.google.com'
        path = '/accounts/ClientLogin'
        if google_email == None or google_password == None:
            google_email, google_password = config.get_google_credentials()

        data = {
            'accountType': 'GOOGLE',
            'Email': google_email,
            'Passwd': google_password,
            'service': 'analytics',
            'source': self.user_agent
        }
        if DEBUG:
            print "Authenticating with %s / %s" % (google_email, google_password)
        data = urllib.urlencode(data)
        response = self.make_request('POST', base_url, path, data=data)
        auth_token = authtoken_pat.search(response.read())
        self.auth_token = auth_token.groups(0)[0]

    def get_accounts(self, start_index=1, max_results=None):
        if not hasattr(self, '_accounts'):
            self._accounts = []
            base_url = 'https://www.google.com'
            path = '/analytics/feeds/accounts/default'
            data = {'start-index': start_index}
            if max_results:
                data['max-results'] = max_results
            data = urllib.urlencode(data)
            response = self.make_request('GET', base_url, path, data=data)
            raw_xml = response.read()
            xml_tree = ElementTree.fromstring(raw_xml)
            accounts = xml_tree.getiterator('{http://www.w3.org/2005/Atom}entry')
            for account in accounts:
                account_data = {
                    'title': account.find('{http://www.w3.org/2005/Atom}title').text,
                    'id': account.find('{http://www.w3.org/2005/Atom}id').text,
                    'updated': account.find('{http://www.w3.org/2005/Atom}updated').text,
                    'table_id': account.find('{http://schemas.google.com/analytics/2009}tableId').text,
                }
                for f in account.getiterator('{http://schemas.google.com/analytics/2009}property'):
                    account_data[f.attrib['name']] = f.attrib['value']
                a = Account(
                    connection=self,
                    title=account_data['title'],
                    id=account_data['id'],
                    updated=account_data['updated'],
                    table_id=account_data['table_id'],
                    account_id=account_data['ga:accountId'],
                    account_name=account_data['ga:accountName'],
                    currency=account_data['ga:currency'],
                    time_zone=account_data['ga:timezone'],
                    profile_id=account_data['ga:profileId'],
                    web_property_id=account_data['ga:webPropertyId'],
                )
                self._accounts.append(a)
        return self._accounts

    def get_account(self, profile_id):
        """Returns an Account object matching the `profile_id` argument."""
        for account in self.get_accounts():
            if account.profile_id == profile_id:
                return account
        raise GoogleAnalyticsClientError("%s is not a valid `profile_id`" % profile_id)

    def make_request(self, method, base_url, path, headers=None, data=''):
        if headers == None:
            headers = {
                'User-Agent': self.user_agent,
                'GData-Version': '2'
            }
            if self.auth_token:
                headers['Authorization'] = 'GoogleLogin auth=%s' % self.auth_token
        else:
            headers = headers.copy()

        if DEBUG:
            print "** Headers: %s" % (headers,)

        if method == 'GET':
            path = '%s?%s' % (path, data)

        if DEBUG:
            print "** Method: %s" % (method,)
            print "** Path: %s" % (path,)
            print "** Data: %s" % (data,)
            print "** URL: %s" % (self.default_host + path)

        if PRETTYPRINT:
            # Doesn't seem to work yet...
            data += "&prettyprint=true"

        if method == 'POST':
            request = urllib2.Request(base_url + path, data, headers)
        elif method == 'GET':
            request = urllib2.Request(base_url + path, headers=headers)

        try:
            response = urllib2.urlopen(request, timeout=TIMEOUT)
        except urllib2.HTTPError, e:
            raise GoogleAnalyticsClientError(e)
        return response
