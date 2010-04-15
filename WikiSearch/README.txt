Provides wiki page/topic name searching & url replies. Generally this is used
for wikis associated with an IRC channel.  Currently handles TWiki, Kwiki,
(including Socialtext Workspace), Moin, Usemod, PmWiki, TracWiki, PhpWiki
and Zwiki wiki types.

This plugin is pure python. The original crude implementation used a
    simple grep of a lynx dumped text file.

To maintain command-level compatibility with previous versions:
    !alias add wiki wikisearch search "$*"
    !alias add wikiurl wikisearch url "$*"

