
# ---
# name: wikipedia-enrich-description
# deployed: true
# title: Wikipedia Topic Description
# description: Returns the first sentence of the Wikipedia entry for a given search term
# params:
#   - name: search
#     type: string
#     description: Text search of Wikipedia
#     required: true
# returns:
#   - name: description
#     type: string
#     description: The first sentence of the Wikipedia entry for the given search term
# examples:
#   - '"Yellowstone National Park"'
#   - '"JS Bach"'
# ---

import json
import urllib
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from cerberus import Validator
from collections import OrderedDict
from bs4 import BeautifulSoup

def flexio_handler(flex):

    # TODO: support language
    language = 'en'


    # get the input
    input = flex.input.read()
    try:
        input = json.loads(input)
        if not isinstance(input, list): raise ValueError
    except ValueError:
        raise ValueError

    # define the expected parameters and map the values to the parameter names
    # based on the positions of the keys/values
    params = OrderedDict()
    params['search'] = {'required': True, 'type': 'string'}
    input = dict(zip(params.keys(), input))

    # validate the mapped input against the validator
    # if the input is valid return an error
    v = Validator(params, allow_unknown = True)
    input = v.validated(input)
    if input is None:
        raise ValueError

    # see here for more info: https://en.wikipedia.org/w/api.php?action=help&modules=query
    # see here to experiment with the api: https://en.wikipedia.org/wiki/Special:ApiSandbox

    # STEP 1: perform a search and get the page id for the top item in the search
    url_query_params = {'action': 'query', 'format': 'json', 'list': 'search', 'srprop': 'timestamp', 'srsearch': input['search']}
    url_query_str = urllib.parse.urlencode(url_query_params)

    url = 'https://en.wikipedia.org/w/api.php?' + url_query_str
    response = requests_retry_session().get(url)
    search_info = response.json()
    search_items = search_info.get('query', {}).get('search', [])

    top_search_item = {}
    if len(search_items) > 0:
        top_search_item = search_items[0]

    top_search_item_page_id = top_search_item.get('pageid')
    if top_search_item_page_id is None:
        flex.output.content_type = "application/json"
        flex.output.write([[""]])
        return

    # STEP 2: get the article for the page id returned by the search
    top_search_item_page_id = str(top_search_item_page_id)
    url = 'https://en.wikipedia.org/w/api.php?format=json&action=query&prop=extracts&explaintext=&exintro=&exsentences=1&pageids=' + top_search_item_page_id
    response = requests_retry_session().get(url)
    article_info = response.json()
    extract = article_info.get('query',{}).get('pages',{}).get(top_search_item_page_id, {}).get('extract', '')

    result = [[extract]]
    flex.output.content_type = "application/json"
    flex.output.write(result)

def requests_retry_session(
    retries=3,
    backoff_factor=0.3,
    status_forcelist=(429, 500, 502, 503, 504),
    session=None,
):
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session
