# K3b — corrected cards (2026-10-14), written after auditing K3 against the reviews and the
# merged code. K3 missed decisive review facts (765378, 768691), turned an out-of-scope note
# into an instruction (764375), and paraphrased the commit message against the final code
# (759321). K3 results are kept as they are; K3b is a separate arm.

## 765378 (pending events at exit)
- There are two places that destroy pending events: `QCoreApplicationPrivate::cleanupThreadData()`
  (under the post-event-list mutex) and `QThreadData::clearEvents()` (iterating unlocked); a
  correct implementation already exists in `removePostedEvents()`. Keep one implementation.
- Shape preferred by reviewers: take the pending events out under the lock, unlock, then delete.
- `~QEvent()` may run arbitrary code, including code that posts new events, so draining must be
  repeated — but with a limit on the number of passes, to avoid an infinite loop; after the
  limit, give up with a warning that the remaining events are leaked.
- Unpost the whole batch before deleting any of it: a destructor may destroy another receiver
  in the same batch.
- The list's offsets (`startOffset`, `insertionOffset`) must be reset too — the application can
  be destroyed from inside event delivery.
- Retaining the list's capacity is a non-goal.

## 768691 (QUrl decode mode)
- `QUrl::ComponentFormattingOption` has free high bits; a private option can live in `qurl_p.h`
  next to the other private recode helpers.
- `qt_urlRecode()` returns 0 when there was nothing to convert, leaving the caller to append the
  input verbatim; a negative return means "refused".
- On refusal, `appendTo` must be left as it was — except that an empty `appendTo` becomes a
  **null** QString: the next change (`QUrl::toLocalFile()`) uses a null result to signal "no
  safe local path". Document that behaviour.
- In the decoder, a byte is unsafe for a local path if it is NUL, `/`, a non-ASCII byte that
  does not form valid UTF-8, or `\` on Windows.
- Reviewers care about doc wording: no contractions in user-visible text.

## 764375 (QThreadPool::clear and QtConcurrent futures)
- Scope of this change: **`QtConcurrent::run()` only.** The map()/filter() path is known to be
  affected too, and the reviewers deliberately keep it out of this change (the bug stays open).
- QRunnables that are not autoDelete have lifetimes managed by their creator: do not change
  how `QThreadPool::clear()` treats them.
- If the future is reported finished without being canceled first, an attached
  `.onCanceled()` continuation does not run; cancel it the same way `start()` already does.

## 759321 (QLockFile EBUSY)
- Keep the order: try `unlink()` first; then close the file descriptor (which drops the lock);
  only if the first `unlink()` failed with EBUSY (seen on NFS), ETXTBSY or EPERM, try `unlink()`
  again after the close.
- One helper should do unlink/close/retry for both callers, and return true **only if the file
  is truly gone** (ENOENT/ENOTDIR count as gone).
- After that helper has closed the handle, it must not be closed again.
- A lock that cannot be removed must not make `lock()` busy-loop without sleeping.
- Removing a lock held by a live process for more than 30 s must not happen just because
  setting native locks failed.
- Ownership re-checks with fstat/stat belong in a separate change — not in this one.
