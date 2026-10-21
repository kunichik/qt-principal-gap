# K3 — "the principal's cards" (frozen 2026-10-12, before any run)

Each card states facts a maintainer of this code would know, taken from the Gerrit review of the
real fix. Facts about the code and its constraints — never the edit itself.

## 778262 (QFuture continuation)
- `runContinuation()` already handles the case where the parent has finished by clearing the
  continuation's link to its parent before running it; the immediate-run path in
  `setContinuation()` is a separate code path.
- A continuation's link to a parent it no longer depends on is what `cancelChain()` and
  `unwrap()` walk.

## 778111 (qUncompress size hint)
- The 4-byte header size is only a hint: the output buffer is grown during decompression anyway,
  so data with a wrong hint must keep working — do not reject it.
- deflate's maximum compression ratio is about 1032:1, which bounds how much output a given
  amount of compressed input can produce.
- Watch signed/unsigned and overflow on **32-bit** platforms (qsizetype is 32-bit there); on
  64-bit, nbytes cannot reach PTRDIFF_MAX/1032.
- Reviewers here reject verbose explanatory comments that state things that are not true.

## 771420 (repeated)
- Qt has overflow-checked arithmetic helpers (`qMulOverflow`, `qAddOverflow`) and `qBadAlloc()`
  for "this allocation cannot be satisfied".
- On overflow, the expected behaviour is what an impossible allocation would do — not silently
  returning an empty or truncated result.
- Both QByteArray and QString have the same pattern; the maintainer prefers the simplest
  readable form.

## 768692 (QUrl::toLocalFile)
- An encoded `%2F` is not a path separator per the URL RFC; QUrl does not treat it as one in
  `resolved()` or for RemoveFileName. Decoding it into `/` in a local path changes the meaning.
- A null QString is an acceptable, documented way for `toLocalFile()` to say "no valid local
  path"; `toString(QUrl::PreferLocalFile)` must still produce something sensible then.
- QUrl's internal recoding already has distinct decode modes; a stricter mode for the
  local-file case fits the existing design.
- An empty path is a legitimate case and must not become null.

## 769883 (QDate ISODate)
- A valid ISO date for QDate is exactly 10 characters, `yyyy-MM-dd`; separators are parsed
  leniently (any punctuation accepted in place of `-`), which is intended and must stay.
- `QDateTime::fromString(..., Qt::ISODate)` and the other `Qt::TextDate` paths already reject
  trailing data; the long-standing lack of a length limit was only backwards compatibility.
- The same applies to `Qt::ISODateWithMs`. Documentation of the format belongs with
  `Qt::DateFormat` (qnamespace.qdoc).

## 776166 (QTimeZone::isValidId)
- IANA's own naming rules (linked in the source comment above `isValidId()`) include: do not
  use the file name components "." and "..".
- Components that merely contain a dot are legitimate and must stay valid.
- The maintainer prefers the per-component decision to depend on explicit inputs (length, dot
  count) rather than on state a lambda mutates while iterating.

## 772702 (QString::insert QL1SV)
- In Qt 4, QLatin1String had no size member, so checking the first character for NUL was how
  emptiness was tested. QLatin1StringView now has a real size and `isEmpty()`.
- A QLatin1StringView may legitimately contain NUL bytes.
- Dereferencing `data()` of an empty view is reading past its end.

# Feature tasks (frozen 2026-10-12, before any run)

## 768691 (QUrl decode mode)
- `QUrl::ComponentFormattingOption` has free high bits; a private option can live in `qurl_p.h`
  next to the other private recode helpers, combined with `QUrl::FullyDecoded`.
- `qt_urlRecode()` returns 0 when there was nothing to convert, leaving the caller to append the
  input verbatim; a negative return is free to mean "refused".
- In the decoder, a byte is unsafe for a local path if it is NUL, `/`, a non-ASCII byte that
  does not form valid UTF-8, or `\` on Windows; on Windows a literal backslash in the input is
  also a problem.
- Reviewers here care about doc wording: no contractions in user-visible text; mention which
  mode is the default.

## 756614 (QThreadStorage::clearLocalData)
- Unlike `setLocalData()`, clearing does not need a QThreadData: if the thread has none (yet or
  any more), clearing must not create one.
- `QCollator` currently works around the missing function; with it, QCollator can go back to a
  value-based QThreadStorage.
- Tests should cover pointer and value variants, a thread that never set data, and the count of
  destroyed objects; style discourages single-letter names.
- One senior maintainer is wary of touching QThreadStorage at all: keep the change minimal.

## 773405 (QCborStreamReader::isNumber/toNumber)
<!-- No reviewer comments exist for this change; this card is written from the commit and the
     surrounding code, so it is closer to the answer than the others. Report K3 here separately. -->
- TinyCBOR already has helpers for reading half, single and double precision values; existing
  `toFloat16()`, `toFloat()`, `toDouble()`, `toInteger()` are the building blocks.
- `toNumber()` may only be called when `isNumber()` is true (assert, like the other `toX()`).
- Negative integers in CBOR can exceed the range of qint64; converting to double must still work.

## 777778 (QMimeDatabase::reload)
- All QMimeDatabase instances share one private instance, so `reload()` is static.
- The periodic check is throttled by a timestamp of the last check; invalidating that timestamp
  makes the next query check at once. Take the private mutex.
- Do not add file watchers or D-Bus: the mtime check is intentional.
- `tst_qmimedatabase` sets `qmime_secondsBetweenChecks` to 0 in two places to work around the
  delay; those should use `reload()`, and the variable then no longer needs exporting.

# Second batch (frozen 2026-10-13, before any run)

## 764375 (QThreadPool::clear and QtConcurrent futures)
- QRunnables that are not autoDelete have lifetimes managed by their creator: a fix must not
  simply delete or take over such runnables.
- If the future is reported finished without being canceled first, an attached
  `.onCanceled()` continuation does not run; it must be canceled the same way `start()`
  already does it.
- The map()/filter() family uses a non-auto-deleting ThreadEngine that is started more than
  once; it is affected too (it also leaks).

## 765378 (pending events at exit)
- There are two places that destroy pending events: `QCoreApplicationPrivate::cleanupThreadData()`
  (under the post-event-list mutex) and `QThreadData::clearEvents()` (iterating unlocked); a
  correct implementation already exists in `removePostedEvents()`.
- Reviewers' preferred shape: swap/move the list out under the lock, unlock, then delete; and
  drain whatever those destructors post in turn.
- The list's offsets (`startOffset`, `insertionOffset`) must be reset too — the application can
  be destroyed from inside event delivery.
- Do not change memory-ordering of unrelated atomics in the same change.

## 754389 (sender vptr race)
- Calling virtual functions (signal resolution, `disconnectNotify()`) on another thread's object
  is only safe from the thread that owns it; that object's derived-class destructors may be
  rewriting its vptr right now.
- When the sender lives in another thread, the notification can be posted as an event to the
  sender's thread — unless that thread can no longer deliver events (e.g. it has finished);
  `~QObjectPrivate()` can discard such an event if the sender is being destroyed.
- `disconnectNotify()` callers outside qtbase exist (qtdeclarative's QQmlNotifierEndpoint,
  qtscxml); document clearly when the call is inline and when it is deferred.

## 750871 (connect() registering meta types)
- The regression came from removing `{ Defined = 1 }` from the `QMetaTypeId2` expansion: that
  fixed *what* was registered but broke *whether* it is registered.
- moc-generated code already solves this with `qTryMetaTypeInterfaceForType()`; reuse it rather
  than inventing a new check.
- Completeness of a type can differ between translation units for the same connect() arguments;
  folding of template instantiations can then pick the wrong version — route the unique type
  through the suitability check into the completeness test.

## 754345 (readElementText recursion)
- This is a security fix: by commit policy it must be minimal — no unrelated refactoring.
- Recursion is not needed: track the nesting level inside the loop.
- The loop is entered with a known nesting level of 1; a do-while expresses that.

## 759321 (QLockFile EBUSY)
- `close()` drops the POSIX locks; the file must be closed before `unlink()`.
- After `releaseLockFile()` closed the handle, it must not be closed again.
- `QFileSystemEngine::renameFile()` already has a link+unlink fallback for `renameat2()`
  returning EINVAL on non-local file systems.
- An EEXIST from the rename must not be treated as success; removing a lock held by a live
  process for more than 30 s must not happen just because setting native locks failed.
