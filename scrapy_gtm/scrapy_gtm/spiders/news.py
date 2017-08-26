# -*- coding: utf-8 -*-
# This package will contain the spiders of your Scrapy project
#
# Please refer to the documentation for information on how to create and manage
# your spiders.
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule
from scrapy.item import Item, Field

def clean(s):
    s = str(s)
    while any(x in s for x in ['\n', '\t']):
        s = s.replace('\n','').replace('\t','')
    s = s.strip('- ')
    return s

class MyItem(Item):
    url = Field()
    news = Field()

class MySpider(CrawlSpider):
    name = 'gtm'
    allowed_domains = ['greentechmedia.com']
    start_urls = [
        'https://www.greentechmedia.com',
                  ]
    
    links_regex_to_follow = [
#         r'https://www.greentechmedia.com',
        
        # For testing purposes: comment all, leave only link bellow uncommented
        r'https://www.greentechmedia.com/articles/read/smart-lighting-ma-alert-digital-lumens-acquired-by-osram',
        ]
        
    links_regex_to_process = [
#         r'https://www.greentechmedia.com/articles/read/[.*]',
        
        # For testing purposes: comment all, leave only link bellow uncommented
        r'https://www.greentechmedia.com/articles/read/smart-lighting-ma-alert-digital-lumens-acquired-by-osram',
        ]

    rules = (Rule(LinkExtractor(allow=links_regex_to_process),
                  callback='handle_news',
                  follow=True),
                Rule(LinkExtractor(allow=links_regex_to_follow),
                  callback='handle_no_news',
                  follow=True), 
             )

    def handle_news(self, response):
        
        item = MyItem()
        item['url'] = response.url
        item['news'] = True
        
        return item
    
    def handle_no_news(self, response):        
        
        item = MyItem()
        item['url'] = response.url
        item['news'] = False
        
        return item
    
    
    
    
    
    
    