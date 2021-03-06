import datetime
import json
import os
import re
import shutil
import sys
import time
import urllib
import urllib2
import webbrowser

import markdown as md

from jinja2 import FileSystemLoader, Environment

# This file is crazy inefficient, however I didn't care because it's only run
# once every few weeks.  Eventually I'll go through and clean it up.

# So, don't judge me for some of the horrible, horrible things I do here.

# TODO:
# - Abstract the jinja stuff; move it to another file
# - Don't keep loading settings!

FOLDER_TEMP = 'app-temp'
FOLDER_REAL = 'app'

settings_new = {}

def compile_home():
    args = {'page': 'home'}

    # Notepads
    to_compile = get_list('notepad_src')[:5]
    notes = []

    template = get_template('notepad_preview.html', render=False)

    for note in to_compile:
        args_np={'template': template, 'filename': note['filename'],
                 'date': note['date'], 'slug': note['slug'], 'preview': True}
        notes.append(render_notepad(note['filename'], args=args_np))

    args['notes'] = notes

    # Articles
    to_compile_article = get_list('magazine_src')[:4]
    articles = []

    template = get_template('magazine_preview.html', render=False)

    for article in to_compile_article:
        articles.append(render_magazine(article['filename'], args={
                'filename': article['filename'],
                'date': article['date'],
                'file': article['filename'],
                'slug': article['slug'],
                'template': template}))

    args['articles'] = articles

    get_template('home.html', args, '%s/index.html' % FOLDER_TEMP)

def compile_page(file):
    args = {'page': file}
    get_template('%s.html' % file, args, '%s/%s.html' % (FOLDER_TEMP, file))

def render_magazine(template, args={}, output=None, render=True):
    if not 'template' in args:
        args['template'] = get_template('magazine.html', render=False)

    if 'slug' in args:
        args['ns'] = "article-%s" % args['slug']

    args['file'] = template

    out_file = None
    if output:
        out_file = re.sub('^/?[-0-9]{11}', '', output)
        out_file = '%s/magazine/%s' % (FOLDER_TEMP, out_file)

    return get_template(('magazine_src', template), args, render=render,
                        output=out_file)

def render_notepad(file, args={}, output=None):
    if 'template' not in args:
        args['template'] = get_template('notepad_single.html', render=False)

    out_file = None
    if output:
        out_file = re.sub('^/?[-0-9]{11}', '', output)
        out_file = '%s/notepad/%s' % (FOLDER_TEMP, out_file)

    return get_template(('notepad_src', file), args=args, output=out_file)

def render_portfolio(file, args={}, output=None):
    #if 'template' not in args:
    #    args['template'] = get_template('notepad_full.html', render=False)

    out_file = None
    if output:
        out_file = re.sub('^/?[-0-9]{11}', '', output)
        out_file = '%s/portfolio/%s.html' % (FOLDER_TEMP, out_file)

    # Move assets
    template_name = output
    if os.path.exists('portfolio_src/%s' % template_name):
        shutil.copytree('portfolio_src/%s' % template_name,
                        '%s/portfolio/%s' % (FOLDER_TEMP, template_name))

    return get_template(('portfolio_src/%s' % file[0], file[1]), args=args, output=out_file)

def generate_bitly(url):
    settings = {}
    with open('settings.json', 'r') as f:
        settings = json.load(f)

    if('bitly_key' not in settings):
        return url

    url_base = "http://api.bitly.com/v3/shorten"
    bitly_url = "%s?longUrl=%s&login=%s&apiKey=%s&format=txt" % (
                url_base, urllib.quote(url), settings['bitly_login'],
                settings['bitly_key'])

    r = urllib2.urlopen(bitly_url)
    return r.readline().strip()

def datetimeformat(value, format='%B %d, %Y'):
    return value.strftime(format)

def markdown(content):
  return md.markdown(content)

def footnoter(value):
    i = 1
    match = "\(\(\(((?:.|\n)*?)\)\)\)"
    link = "<sup id='fnc-%s'>[<a href='#fn-%s'>%s</a>]</sup>"
    footnote = "<li id='fn-%s'>%s [<a href='#fnc-%s'>&#x21A9;</a>]</li>"

    fns = []

    while re.search(match, value):
        footnote_text = re.search(match, value)
        value = re.sub(match, link % (i, i, i), value, 1)
        fns.append(footnote % (i, footnote_text.group(1), i))
        i += 1

    if fns:
        value = value + ("<ol class='footnotes'>%s</ol>" % '\n'.join(fns))
    return value

def namespacer(value, namespace, f, section="magazine"):
    value = re.sub('#namespace', '#%s' % namespace, value)
    value = re.sub('assets/', '%s/%s/' % (section, f.split('.')[0]), value)
    return value

def escaper(text):
    codes = [
            ('&', '&amp;'),
            ('<', '&lt;'),
            ('>', '&gt;'),
            ('"', '&quot;'),
            ("'", '&#39;'),
            ]
    for code in codes:
        text = text.replace(code[0], code[1])
    return text

def url(url, use_base=False, bitly=False):
    settings = {}
    with open('settings.json', 'r') as f:
        settings = json.load(f)

    url = re.sub('[-0-9]{11}', '', url)

    if settings['prod']:
        url = re.sub('\.html', '', url)
        url = re.sub('^/?magazine/', '/m/', url)
        url = re.sub('^/?notepad/', '/n/', url)

    url = '/%s' % re.sub('^/', '', url)

    if (use_base or bitly) and 'base' in settings:
        base = re.sub('/$', '', settings['base'])
        url = re.sub('^/', '', url)
        url = ('%s/%s' % (base, url))

        if bitly:
            url = generate_bitly(url)

    return url

# By weight, not date. TODO: Combine with get_list. Too lazy now :)
def get_list_weight(*folders):
    return_list = []

    for folder in folders:
        to_compile = os.listdir(folder)
        to_compile = [f for f in to_compile
                      if re.match("\d+-(.*)(.html)?", f)]

        for f in to_compile:
            d = re.search('(\d+)-(.*)(.html)?', f)
            slug = d.group(2)
            return_list.append({'weight': int(d.group(1)), 'slug':slug, 'filename':f,
                                'folder': folder})

    return_list.sort(key=lambda d: d['weight'])
    return return_list

def get_list(*folders):
    return_list = []

    for folder in folders:
        to_compile = os.listdir(folder)
        to_compile = [f for f in to_compile
                      if re.match("\d{4}-\d{2}-\d{2}-(.*).html", f)]

        for f in to_compile:
            d = re.search('(\d{4})-(\d{2})-(\d{2})-(.*).html', f)
            date = datetime.datetime(int(d.group(1)), int(d.group(2)), int(d.group(3)))
            slug = d.group(4)
            date_sort = time.mktime(date.timetuple())
            return_list.append({'date':date, 'slug':slug, 'filename':f,
                'folder': folder})

    return_list.sort(reverse=True, key=lambda d: time.mktime(d['date'].timetuple()))
    return return_list

def compile_magazines():
    to_compile = get_list('magazine_src')

    for (i, article) in enumerate(to_compile):
        nav_prev = nav_next = ""

        # gosh this is crazy inefficient.
        if i > 0:
            template = get_template('magazine_nav.html', render=False)
            a = to_compile[i - 1]
            nav_next = render_magazine(a['filename'], args={
                        'filename': a['filename'],
                        'date':a['date'],
                        'file': a['filename'],
                        'slug': a['slug'],
                        'type': 'next',
                        'template': template})
        if i < len(to_compile) - 1:
            template = get_template('magazine_nav.html', render=False)
            a = to_compile[i + 1]
            nav_prev = render_magazine(a['filename'], args={
                        'filename': a['filename'],
                        'date': a['date'],
                        'file': a['filename'],
                        'slug': a['slug'],
                        'type': 'prev',
                        'template': template})

        settings = {}
        with open('settings.json', 'r') as f:
            settings = json.load(f)

        args = {'date': article['date'],
                'slug': article['slug'],
                'page': 'magazine',
                'filename': article['filename'],
                'nav_next': nav_next,
                'nav_prev': nav_prev,
                'is_prod': settings['prod']}

        # Move assets
        template_name = article['filename'].split('.')[0]
        if os.path.exists('magazine_src/%s' % template_name):
            shutil.copytree('magazine_src/%s' % template_name,
                            '%s/magazine/%s' % (FOLDER_TEMP, template_name))

        render_magazine(article['filename'], args, article['filename'])

def get_block(template, block=''):
    return ''.join([i for i in template.blocks.get(block)({})])

def compile_rss(category=None, desc=None, title=None):
    to_compile = get_list('notepad_src', 'magazine_src')
    notes = []
    first_date = False
    for note in to_compile:
        if not first_date:
            first_date = note['date']
        template = get_template('feed-item.rss', render=False)
        if note['folder'] == 'notepad_src':
            f = render_notepad(note['filename'], args={'template': template,
                'filename': note['filename'], 'date': note['date'],
                'slug': note['slug'], 'folder': 'notepad' })
        else:
            f = render_magazine(note['filename'], args={'template': template,
                'filename': note['filename'], 'date': note['date'],
                'slug': note['slug'], 'folder': 'magazine' })

        # Should use pyquery...
        if not category or re.search('<category>%s<\/category>' % category, f):
            notes.append(f)

    name = category if category else 'feed'
    if not desc:
        desc = 'Blog posts and articles by Gregory Koberger'

    get_template('feed.rss', args={'notes': notes, 'date': first_date,
                                   'title': title, 'desc': desc},
                 output='%s/%s.rss' % (FOLDER_TEMP, name))

def compile_notepads():
    to_compile = get_list('notepad_src')

    settings = {}
    with open('settings.json', 'r') as f:
        settings = json.load(f)

    notes = []
    template_full = get_template('notepad_full.html', render=False)

    for (i, note) in enumerate(to_compile):
        nav_prev = nav_next = ""

        # gosh this is crazy inefficient.
        if i > 0:
            template = get_template('notepad_nav.html', render=False)
            a = to_compile[i - 1]
            nav_next = render_notepad(a['filename'], args={
                        'filename': a['filename'],
                        'date':a['date'],
                        'file': a['filename'],
                        'slug': a['slug'],
                        'type': 'next',
                        'template': template})
        if i < len(to_compile) - 1:
            template = get_template('notepad_nav.html', render=False)
            a = to_compile[i + 1]
            nav_prev = render_notepad(a['filename'], args={
                        'filename': a['filename'],
                        'date': a['date'],
                        'file': a['filename'],
                        'slug': a['slug'],
                        'type': 'prev',
                        'template': template})

        args = {'date': note['date'], 'slug': note['slug'],
                'is_prod': settings['prod'], 'filename': note['filename'],
                'nav_prev': nav_prev, 'nav_next': nav_next}

        f = render_notepad(note['filename'], args=args)
        notes.append(f)

        args['page'] = 'notebook'
        args['template'] = template_full
        render_notepad(note['filename'], args, note['filename'])

    get_template('notepad.html', args={'notes': notes, 'page': 'notebook'}, output='%s/notepad.html' % FOLDER_TEMP)

def compile_portfolio():
    to_compile = get_list_weight('portfolio_src')

    settings = {}
    with open('settings.json', 'r') as f:
        settings = json.load(f)

    portfolios = []
    template_full = get_template('portfolio_full.html', render=False)

    for (i, portfolio) in enumerate(to_compile):
        nav_prev = nav_next = ""

        args = {'slug': portfolio['slug'],
                'is_prod': settings['prod'], 'filename': portfolio['filename']}

        #f = render_portfolio(portfolio['filename'], args=args)
        #portfolios.append(f)

        args['page'] = 'portfolio'
        args['template'] = template_full
        render_portfolio((portfolio['filename'], "index.html"), args, portfolio['filename'])

    #get_template('portfolio.html', args={'notes': notes, 'page': 'notebook'}, output='%s/notepad.html' % FOLDER_TEMP)

def get_template(template, args={}, output=None, render=True, stop=False):
    loader = False
    template_file = False

    if stop:
        import pdb; pdb.set_trace()

    if isinstance(template, tuple):
        loader = FileSystemLoader('%s/' % template[0])
        template_file = template[1]
    else:
        loader = FileSystemLoader('templates/')
        template_file = template

    env = Environment(loader=loader)
    env.filters['footnoter'] = footnoter
    env.filters['markdown'] = markdown
    env.filters['url'] = url
    env.filters['escaper'] = escaper
    env.filters['namespacer'] = namespacer
    env.filters['datetimeformat'] = datetimeformat
    env.filters['urlencode'] = urllib.quote

    settings = {}
    with open('settings.json', 'r') as f:
        settings = json.load(f)

    env.globals = {'base': settings['base'],
                   'year': 2011,
                   'article_url': get_list('magazine_src')[0]['filename']}

    template_object = env.get_template(template_file)

    if not render:
        return template_object

    rendered = template_object.render(args)

    if output:
        with open(output, 'w') as o:
           rendered = unicode(rendered)
           rendered = rendered.replace(u"\xe9", " ")
           rendered = rendered.replace(u"\u2019", " ")
           rendered = rendered.replace(u"\u00A0", " ")

           o.write(unicode(rendered))

    return rendered

#def render_tempate(template, args):
    #args['base'] = 'file:///Users/gkoberger/Sites/gkoberger/'
    #args['year'] = 2011

    #return template.render(args)

def swap_folder(src, dst):
    # First, clean out the destination folder
    for the_file in os.listdir(dst):
        file_path = os.path.join(dst, the_file)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
            else:
                shutil.rmtree(file_path)
        except Exception, e:
            print e

    # Now, copy everything over
    for the_file in os.listdir(src):
        src_path = os.path.join(src, the_file)
        dst_path = os.path.join(dst, the_file)
        try:
            if os.path.isfile(src_path):
                shutil.copy(src_path, dst_path)
            else:
                shutil.copytree(src_path, dst_path)
        except Exception, e:
            print e

def move_base():
    swap_folder('app-base', FOLDER_TEMP)

    shutil.copytree('js', '%s/js' % FOLDER_TEMP)
    shutil.copytree('css', '%s/css' % FOLDER_TEMP)
    shutil.copytree('images', '%s/images' % FOLDER_TEMP)


if __name__ == '__main__':
    shutil.rmtree(FOLDER_TEMP, True)
    os.mkdir(FOLDER_TEMP)

    move_base()

    compile_notepads()
    compile_magazines()
    compile_portfolio()
    compile_home()

    compile_page('p404')
    compile_page('about')
    compile_page('about_new')
    compile_page('portfolio')
    compile_page('resume')

    compile_rss()
    compile_rss('mozilla', desc="Mozilla-related blog posts", title="Mozilla")

    # Move from temp folder and delete it
    swap_folder(FOLDER_TEMP, FOLDER_REAL)
    shutil.rmtree(FOLDER_TEMP, True)

