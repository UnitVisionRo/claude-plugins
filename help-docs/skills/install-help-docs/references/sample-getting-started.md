---
title: Getting started
order: 10
group: Basics
summary: How to find your way around and where to get help.
routes:
  - /
---

# Getting started

This page is the first topic of the built-in documentation. Replace it with the documents your
own application needs — one per screen — and delete this one once you have something real.

## Finding help

Every page has a **Help** button in the bar at the top. It opens the document written for the
page you are on, without taking you away from it. If a page has no document of its own yet, the
button shows the list of topics instead.

The same documentation is available in full on the help page, where the topics are listed on the
left and the chosen one is shown on the right.

## Searching

The search box above the topic list looks through the text of every document, not just the
titles. Type at least two letters; results show the section the words were found in, with the
matching phrase highlighted, and choosing one opens the document scrolled to that exact section.

Endings do not matter — searching for `invoice` also finds `invoices`.

## Writing documentation

The documents are Markdown files in `docs/help/`, kept in git next to the code. Each file
becomes one topic, and its `routes:` entry is what ties it to a page of the application.

See [Searching](#searching) above for an example of a link to another section of the same
document; links to other documents, to application pages and to external addresses are all
checked when the documentation is generated, so a broken one stops the build instead of
reaching a user.
