
# ---
# name: wikipedia-enrich-org
# deployed: true
# title: Wikipedia Organization Enrichment
# description: Returns profile information of an organization from Wikipedia based on given search term
# params:
#   - name: search
#     type: string
#     description: Text search of Wikipedia
#     required: true
#   - name: properties
#     type: array
#     description: The properties to return (defaults to 'description'). See "Returns" for a listing of the available properties.
#     required: false
# returns:
#   - name: label
#     type: string
#     description: A label for the organization
#   - name: description
#     type: string
#     description: A description of the organization (default)
#   - name: wikipedia_url
#     type: string
#     description: The wikipedia url for the organization
#   - name: website
#     type: string
#     description: The website for the organization
#   - name: official_name
#     type: string
#     description: The official name for the organization
#   - name: short_name
#     type: string
#     description: A short name for the organization
#   - name: motto
#     type: string
#     description: The organization's motto
#   - name: inception
#     type: string
#     description: The date the organization was founded
#   - name: country
#     type: string
#     description: The country the organization is based in
#   - name: twitter_id
#     type: string
#     description: The organization's twitter id
#   - name: instagram_id
#     type: string
#     description: The organization's instagram id
#   - name: reddit_id
#     type: string
#     description: The organization's reddit id
#   - name: bloomberg_id
#     type: string
#     description: The organization's bloomberg id
#   - name: updated_dt
#     type: string
#     description: The date the information was last updated
# examples:
#   - '"Google"'
#   - '"Apple"'
# ---

import json
import requests
import urllib
import itertools
from datetime import *
from decimal import *
from cerberus import Validator
from collections import OrderedDict

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
    params['properties'] = {'required': False, 'validator': validator_list, 'coerce': to_list, 'default': 'description'}
    input = dict(zip(params.keys(), input))

    # validate the mapped input against the validator
    # if the input is valid return an error
    v = Validator(params, allow_unknown = True)
    input = v.validated(input)
    if input is None:
        raise ValueError

    # default property list
    default_properties = OrderedDict()
    default_properties['label'] = ''
    default_properties['description'] = ''
    default_properties['wikipedia_url'] = ''
    default_properties['website'] = ''
    default_properties['official_name'] = ''
    default_properties['short_name'] = ''
    default_properties['motto'] = ''
    default_properties['inception'] = ''
    default_properties['country'] = ''
    default_properties['twitter_id'] = ''
    default_properties['instagram_id'] = ''
    default_properties['reddit_id'] = ''
    default_properties['bloomberg_id'] = ''
    default_properties['updated_dt'] = ''

    try:

        # see here for general information about the wikidata api: https://www.wikidata.org/wiki/Wikidata:Data_access
        # see here for list of sorted properties: https://www.wikidata.org/wiki/MediaWiki:Wikibase-SortedProperties

        # STEP 1: make an initial search request to find the most relevant item
        # https://www.wikidata.org/w/api.php?action=wbsearchentities&language=en&search=:search_term
        url_query_params = {'action': 'wbsearchentities', 'language': language, 'format': 'json', 'search': input['search']}
        url_query_str = urllib.parse.urlencode(url_query_params)

        url = 'https://www.wikidata.org/w/api.php?' + url_query_str
        response = requests.get(url)
        search_info = response.json()
        search_items = search_info.get('search', [])

        if len(search_items) == 0:
            flex.output.content_type = "application/json"
            flex.output.write([[""]])
            return

        search_first_item_id = search_items[0].get('id','')

        # STEP 2: get the info about the item
        # https://www.wikidata.org/w/api.php?action=wbgetentities&sites=enwiki&props=claims&format=json&ids=:id
        props = 'info|sitelinks|sitelinks/urls|labels|descriptions|claims|datatype'
        url_query_params = {'action': 'wbgetentities', 'sites': 'enwiki', 'props': props, 'format': 'json', 'ids': search_first_item_id}
        url_query_str = urllib.parse.urlencode(url_query_params)

        url = 'https://www.wikidata.org/w/api.php?' + url_query_str
        response = requests.get(url)
        content = response.json()

        # TODO:
        # confirm we have an organization

        # STEP 3: get primary item info and additional info
        item_primary_info = get_basic_info(content, search_first_item_id, language)
        item_claim_info = get_claim_info(content, search_first_item_id, language)

        # STEP 4: make an additional lookup to find out the info from the wikipedia entity values
        # https://www.wikidata.org/w/api.php?action=wbgetentities&sites=enwiki&props=claims&format=json&ids=:id
        props = 'labels'
        search_ids = [i.get('datavalue',{}).get('value',{}).get('id','') for i in item_claim_info if i.get('datavalue',{}).get('type') == 'wikibase-entityid']
        search_ids = '|'.join(search_ids)
        url_query_params = {'action': 'wbgetentities', 'sites': 'enwiki', 'props': props, 'format': 'json', 'ids': search_ids}
        url_query_str = urllib.parse.urlencode(url_query_params)

        url = 'https://www.wikidata.org/w/api.php?' + url_query_str
        response = requests.get(url)
        content = response.json()

        # STEP 5: use the info from the additional lookup to populate the values in the item info
        item_claim_info_enriched = [update_claim_info(i, content, language) for i in item_claim_info]

        # STEP 6: merge the primary info and the enriched info
        item_info_lookup = {}
        for i in item_primary_info:
            item_info_lookup[i['name']] = i.get('value','')
        for i in item_claim_info:
            item_info_lookup[i['name']] = i.get('value','')

        # get the properties to return
        properties = [p.lower().strip() for p in input['properties']]

        # if we have a wildcard, get all the properties
        if len(properties) == 1 and properties[0] == '*':
            properties = list(default_properties.keys())

        # build up the result
        result = [[item_info_lookup.get(p,'') or '' for p in properties]]

        # return the results
        result = json.dumps(result, default=to_string)
        flex.output.content_type = "application/json"
        flex.output.write(result)

    except:
        raise RuntimeError

def update_claim_info(claim_info, object, language):
    value_type = claim_info.get('datavalue',{}).get('type')
    if value_type == 'wikibase-entityid':
        entity_id_lookup = claim_info.get('datavalue',{}).get('value',{}).get('id','')
        claim_info['value'] = object.get('entities',{}).get(entity_id_lookup,{}).get('labels',{}).get(language, {}).get('value','')
    if value_type == 'time':
        claim_info['value'] = claim_info.get('datavalue',{}).get('value',{}).get('time','')
    if value_type == 'quantity':
        claim_info['value'] = claim_info.get('datavalue',{}).get('value',{}).get('amount','')
    if value_type == 'monolingualtext':
        claim_info['value'] = claim_info.get('datavalue',{}).get('value',{}).get('text','')
    if value_type == 'string':
        claim_info['value'] = claim_info.get('datavalue',{}).get('value','')
    return claim_info

def get_basic_info(object, item_id, language):
    return [
        {'name': 'label', 'type': 'string', 'value': object.get('entities',{}).get(item_id,{}).get('labels',{}).get(language, {}).get('value','')},
        {'name': 'description', 'type': 'string', 'value': object.get('entities',{}).get(item_id,{}).get('descriptions',{}).get(language, {}).get('value','')},
        {'name': 'updated_dt', 'type': 'datetime', 'value': object.get('entities',{}).get(item_id,{}).get('modified','')},
        {'name': 'wikipedia_url', 'type': 'string', 'value': object.get('entities',{}).get(item_id,{}).get('sitelinks',{}).get(language+'wiki',{}).get('url','')}
    ]

def get_claim_info(object, item_id, language):

    properties = [
        #{'name': 'logo_url', 'prop': 'P154'},
        {'name': 'website', 'prop': 'P856'},
        {'name': 'official_name', 'prop': 'P1448'},
        {'name': 'short_name', 'prop': 'P1813'},
        {'name': 'motto', 'prop': 'P1451'},
        {'name': 'inception', 'prop': 'P571'},
        {'name': 'country', 'prop': 'P17'},
        #{'name': 'stock_ticker', 'prop': 'P414'},
        {'name': 'twitter_id', 'prop': 'P2002'},
        {'name': 'bloomberg_id', 'prop': 'P3052'},
        {'name': 'reddit_id', 'prop': 'P4265'},
        {'name': 'instagram_id', 'prop': 'P2003'}
    ]

    updated_properties = [{
        'name': p['name'],
        'prop': p['prop'],
        'datavalue': object.get('entities',{}).get(item_id,{}).get('claims').get(p['prop'],[{}])[0].get('mainsnak',{}).get('datavalue',{})
    } for p in properties]

    return updated_properties

def validator_list(field, value, error):
    if isinstance(value, str):
        return
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, str):
                error(field, 'Must be a list with only string values')
        return
    error(field, 'Must be a string or a list of strings')

def to_string(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (Decimal)):
        return str(value)
    return value

def to_list(value):
    # if we have a list of strings, create a list from them; if we have
    # a list of lists, flatten it into a single list of strings
    if isinstance(value, str):
        return value.split(",")
    if isinstance(value, list):
        return list(itertools.chain.from_iterable(value))
    return None
