// Shared Executive Report Theme
#let brand-color = rgb("#0F172A")
#let primary-blue = rgb("#1E40AF")
#let accent-teal = rgb("#0D9488")
#let bg-soft = rgb("#F8FAFC")
#let border-color = rgb("#E2E8F0")

#let report-theme(
  title: "Document Title",
  subtitle: "Document Subtitle",
  author: "Author",
  date: "August 2026",
  body
) = {
  set document(title: title, author: author)
  set page(
    paper: "a4",
    margin: (x: 2cm, top: 2.5cm, bottom: 2.5cm),
    header: context {
      if counter(page).get().first() > 1 [
        #grid(
          columns: (1fr, auto),
          align(left)[#text(size: 8.5pt, fill: rgb("#64748B"))[#title]],
          align(right)[#text(size: 8.5pt, fill: rgb("#64748B"))[Technical Report]]
        )
        #v(-4pt)
        #line(length: 100%, stroke: 0.5pt + border-color)
      ]
    },
    footer: context {
      if counter(page).get().first() > 1 [
        #line(length: 100%, stroke: 0.5pt + border-color)
        #v(2pt)
        #grid(
          columns: (1fr, auto),
          align(left)[#text(size: 8.5pt, fill: rgb("#64748B"))[CONFIDENTIAL]],
          align(right)[#text(size: 8.5pt, fill: rgb("#64748B"), weight: "bold")[Page #counter(page).get().first()]]
        )
      ]
    }
  )

  set text(font: ("Liberation Sans", "Helvetica"), size: 10pt, fill: rgb("#334155"))

  align(center)[
    #block(fill: brand-color, inset: (x: 20pt, y: 14pt), radius: 4pt)[
      #text(fill: white, size: 9pt, weight: "bold")[EXECUTIVE TECHNICAL REPORT]
    ]
    #v(0.8cm)
    #text(size: 22pt, weight: "bold", fill: brand-color)[#title]
    #v(0.4cm)
    #text(size: 11pt, fill: rgb("#475569"))[#subtitle]
    #v(0.8cm)
    #line(length: 40%, stroke: 1.5pt + primary-blue)
    #v(0.4cm)
    #text(size: 8.5pt, fill: rgb("#64748B"))[Author: #author | Date: #date]
  ]

  v(1cm)
  body
}

#let callout(title: "NOTE", body) = {
  block(
    fill: rgb("#F1F5F9"),
    stroke: (left: 4pt + accent-teal),
    inset: (x: 14pt, y: 10pt),
    radius: (right: 4pt),
    width: 100%,
    [
      #text(weight: "bold", size: 9pt, fill: accent-teal)[#title]
      #v(2pt)
      #text(size: 9.5pt)[#body]
    ]
  )
}
