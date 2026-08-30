;;; episteme-citations.el --- citation navigation for Episteme  -*- lexical-binding: t; -*-

;; This file is part of the Episteme knowledge repository.

;;; Commentary:

;; This library connects Org/Citar citations, Bibliotheca's generated catalogue,
;; and Episteme's rebuildable Ciao relation index.  Org remains authoritative:
;; reverse navigation invokes bin/query-relations, which rebuilds the disposable
;; facts before returning exact citation or relation occurrences.
;;
;; Add this directory to `load-path', require `episteme-citations', configure
;; Citar to use `episteme-open-bibliotheca-entry', and bind
;; `episteme-citation-dwim' according to personal preference.

;;; Code:

(require 'org)
(require 'subr-x)

(declare-function citar-citation-at-point "citar")
(declare-function citar-key-at-point "citar")
(declare-function citar-open-entry "citar")

(defgroup episteme-citations nil
  "Citation navigation between Episteme and Bibliotheca."
  :group 'org)

(defcustom episteme-directory
  (expand-file-name "~/knowledge/episteme")
  "Root directory of the Episteme repository."
  :type 'directory
  :group 'episteme-citations)

(defcustom episteme-bibliotheca-file
  (expand-file-name "~/knowledge/bibliotheca/zotero-library.org")
  "Generated Bibliotheca Org catalogue."
  :type 'file
  :group 'episteme-citations)

(defcustom episteme-relation-query
  (expand-file-name "bin/query-relations" episteme-directory)
  "Executable used to query Episteme relation occurrences."
  :type 'file
  :group 'episteme-citations)

(defun episteme-open-bibliotheca-entry (citekey)
  "Open CITEKEY's generated entry in Bibliotheca."
  (find-file episteme-bibliotheca-file)
  (widen)
  (goto-char (point-min))
  (if (re-search-forward
       (format "^:CITEKEY:[ \t]+%s[ \t]*$" (regexp-quote citekey))
       nil t)
      (progn
        (org-back-to-heading t)
        (org-fold-show-context)
        (org-fold-show-entry))
    (user-error "Citation key not found in Bibliotheca: %s" citekey)))

(defun episteme--bibliotheca-entry-citekey ()
  "Return the current Bibliotheca item's citation key, if any."
  (when (and buffer-file-name
             (file-exists-p episteme-bibliotheca-file)
             (file-equal-p buffer-file-name episteme-bibliotheca-file))
    (save-excursion
      (when (org-before-first-heading-p)
        (user-error "Point is not in a Bibliotheca item"))
      (org-back-to-heading t)
      (org-entry-get nil "CITEKEY"))))

(defun episteme--parse-reference-row (row)
  "Parse one tab-separated relation query ROW into an occurrence plist."
  (let* ((fields (split-string row "\t"))
         (predicate (nth 0 fields))
         (path (nth 1 fields))
         (line (and (nth 2 fields) (string-to-number (nth 2 fields))))
         (column (and (nth 3 fields) (string-to-number (nth 3 fields))))
         (locator (nth 4 fields)))
    (when (and predicate path line (> line 0) column (> column 0) locator)
      (list :predicate predicate :path path :line line :column column
            :locator (unless (string-empty-p locator) locator)))))

(defun episteme--references-to (citekey)
  "Return occurrence plists for Episteme references to CITEKEY."
  (unless (file-executable-p episteme-relation-query)
    (user-error "Relation query is not executable: %s" episteme-relation-query))
  (with-temp-buffer
    (let* ((default-directory episteme-directory)
           (status (process-file episteme-relation-query nil t nil
                                 "references" citekey)))
      (unless (zerop status)
        (user-error "Relation query failed: %s"
                    (string-trim (buffer-string))))
      (delq nil
            (mapcar #'episteme--parse-reference-row
                    (split-string (buffer-string) "\n" t))))))

(defun episteme--reference-label (reference)
  "Return a completion label for an Episteme REFERENCE occurrence."
  (let ((predicate (replace-regexp-in-string
                    "_" "-" (plist-get reference :predicate)))
        (locator (plist-get reference :locator)))
    (format "%s | %s%s | %d:%d"
            (plist-get reference :path)
            predicate
            (if locator (format " %s" locator) "")
            (plist-get reference :line)
            (plist-get reference :column))))

(defun episteme-open-referencing-note (citekey)
  "Open an Episteme reference occurrence for CITEKEY."
  (let* ((references (episteme--references-to citekey))
         (candidates
          (mapcar (lambda (reference)
                    (cons (episteme--reference-label reference) reference))
                  references))
         (reference
          (cond
           ((null references)
            (user-error "No Episteme note references %s" citekey))
           ((null (cdr references)) (car references))
           (t (cdr (assoc (completing-read "Episteme reference: "
                                           candidates nil t)
                          candidates))))))
    (find-file (expand-file-name (plist-get reference :path)
                                 episteme-directory))
    (widen)
    (goto-char (point-min))
    (forward-line (1- (plist-get reference :line)))
    (forward-char (1- (plist-get reference :column)))
    (when (fboundp 'org-fold-show-context)
      (org-fold-show-context))))

(defun episteme-citation-dwim ()
  "Navigate between an Episteme citation and its Bibliotheca entry.
In a Bibliotheca item, open a referencing Episteme occurrence.  Elsewhere, open
the citation at point or select a reference through Citar."
  (interactive)
  (if-let ((citekey (episteme--bibliotheca-entry-citekey)))
      (episteme-open-referencing-note citekey)
    (if-let ((citekey (or (citar-key-at-point)
                          (car (citar-citation-at-point)))))
        (citar-open-entry citekey)
      (call-interactively #'citar-open-entry))))

(provide 'episteme-citations)
;;; episteme-citations.el ends here
