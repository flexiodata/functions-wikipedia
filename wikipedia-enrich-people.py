
# ---
# name: wikipedia-enrich-people
# deployed: true
# title: Wikipedia People Enrichment
# description: Returns profile information of a person from Wikipedia based on given search term
# params:
#   - name: search
#     type: string
#     description: Text search of Wikipedia
#     required: true
#   - name: properties
#     type: array
#     description: The properties to return (defaults to 'description'). See "Notes" for a listing of the available properties.
#     required: false
# examples:
#   - '"Teddy Roosevelt"'
#   - '"JS Bach"'
# notes: |
#   The following properties are allowed:
#     * `label`: a label for the person
#     * `description`: a description of the person
#     * `wikipedia_url`: wikipedia url for the person
#     * `gender`: the person's gender
#     * `birth_name`: the person's birth name
#     * `given_name`:  the person's given (first) name
#     * `family_name`: the person's family (last) name
#     * `native_name`: the person's native name
#     * `birth_date`: the person's birth date
#     * `death_date`: the person's death date
#     * `birth_place`: the person's birth place
#     * `death_place`: the person's death place
#     * `religion`: the person's religion
#     * `citizenship`: the person's country of citizenship
#     * `native_language`: the person's native language
#     * `father`: the person's father
#     * `mother`: the person's mother
#     * `spouse`: the person's spouse
#     * `residence`: the person's place of residence
#     * `occupation`:  the person's occupation
#     * `education`: the person's education
#     * `net_worth`: the person's net worth
#     * `twitter_id`: the person's twitter id
#     * `instagram_id`: the person's instagram id
#     * `reddit_id`: the person's reddit id
#     * `bloomberg_id`: the person's bloomberg id
#     * `updated_dt`: date the information was last updated
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

    default_properties = OrderedDict()
    default_properties['label'] = ''
    default_properties['description'] = ''
    default_properties['wikipedia_url'] = ''
    default_properties['gender'] = ''
    default_properties['birth_name'] = ''
    default_properties['given_name'] = ''
    default_properties['family_name'] = ''
    default_properties['native_name'] = ''
    default_properties['birth_date'] = ''
    default_properties['death_date'] = ''
    default_properties['birth_place'] = ''
    default_properties['death_place'] = ''
    default_properties['religion'] = ''
    default_properties['citizenship'] = ''
    default_properties['native_language'] = ''
    default_properties['father'] = ''
    default_properties['mother'] = ''
    default_properties['spouse'] = ''
    default_properties['residence'] = ''
    default_properties['occupation'] = ''
    default_properties['education'] = ''
    default_properties['net_worth'] = ''
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
        # confirm we have a human
        # instanceof (P31) is Q5 (human)

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
        {'name': 'gender', 'prop': 'P21'},
        {'name': 'birth_name', 'prop': 'P1477'},
        {'name': 'given_name', 'prop': 'P735'},
        {'name': 'family_name', 'prop': 'P734'},
        {'name': 'native_name', 'prop': 'P1559'},
        {'name': 'birth_date', 'prop': 'P569'},
        {'name': 'death_date', 'prop': 'P570'},
        {'name': 'birth_place', 'prop': 'P19'},
        {'name': 'death_place', 'prop': 'P20'},
        {'name': 'religion', 'prop': 'P140'},
        {'name': 'citizenship', 'prop': 'P27'},
        {'name': 'native_language', 'prop': 'P103'},
        {'name': 'father', 'prop': 'P22'},
        {'name': 'mother', 'prop': 'P25'},
        {'name': 'spouse', 'prop': 'P26'},
        #{'name': 'children', 'prop': 'P40'},
        #{'name': 'children_count', 'prop': 'P1971'},
        {'name': 'residence', 'prop': 'P551'},
        {'name': 'occupation', 'prop': 'P106'},
        {'name': 'education', 'prop': 'P69'},
        {'name': 'net_worth', 'prop': 'P2218'},
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
