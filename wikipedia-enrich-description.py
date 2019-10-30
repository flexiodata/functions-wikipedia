
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
# examples:
#   - '"Yellowstone National Park"'
#   - '"JS Bach"'
# notes:
# ---

import json
import requests
from cerberus import Validator
from collections import OrderedDict
from bs4 import BeautifulSoup

def flexio_handler(flex):

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

    try:

        # see here for more info: https://en.wikipedia.org/w/api.php?action=help&modules=query
        # see here to experiment with the api: https://en.wikipedia.org/wiki/Special:ApiSandbox

        # STEP 1: perform a search and get the page id for the top item in the search
        search = input['search']
        url = 'https://en.wikipedia.org/w/api.php?action=query&format=json&list=search&srprop=timestamp&srsearch=' + search
        response = requests.get(url)
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
        response = requests.get(url)
        article_info = response.json()
        extract = article_info.get('query',{}).get('pages',{}).get(top_search_item_page_id, {}).get('extract', '')

        result = [[extract]]
        flex.output.content_type = "application/json"
        flex.output.write(result)

    except:
        raise RuntimeError
