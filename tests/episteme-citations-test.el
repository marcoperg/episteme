;;; episteme-citations-test.el --- tests for Episteme citation UI  -*- lexical-binding: t; -*-

(require 'ert)
(require 'episteme-citations)

(ert-deftest episteme-parse-reference-row-with-locator ()
  (should
   (equal
    (episteme--parse-reference-row
     "cites\tnotes/example.org\t12\t34\tp. 42")
    '(:predicate "cites" :path "notes/example.org" :line 12 :column 34
      :locator "p. 42"))))

(ert-deftest episteme-parse-reference-row-without-locator ()
  (should
   (equal
    (episteme--parse-reference-row
     "informed_by\tnotes/example.org\t4\t1\t")
    '(:predicate "informed_by" :path "notes/example.org" :line 4 :column 1
      :locator nil))))

(ert-deftest episteme-parse-reference-row-preserves-dash-locator ()
  (should
   (equal
    (episteme--parse-reference-row
     "cites\tnotes/example.org\t12\t34\t-")
    '(:predicate "cites" :path "notes/example.org" :line 12 :column 34
      :locator "-"))))

(ert-deftest episteme-reference-label-describes-exact-occurrence ()
  (should
   (equal
    (episteme--reference-label
     '(:predicate "cites" :path "notes/example.org" :line 12 :column 34
       :locator "p. 42"))
    "notes/example.org | cites p. 42 | 12:34")))

(provide 'episteme-citations-test)
;;; episteme-citations-test.el ends here
