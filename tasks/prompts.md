# Symptom-only prompts (frozen before any run)

Common suffix for every prompt:
"The code is qtbase (Qt 6, dev branch). A Debug developer build is in ~/qtexp/b3 (build with
`ninja -C ~/qtexp/b3 <target>`; autotests are under tests/auto). Find the root cause and fix it
in the library source. You may add or change tests."

## 778262
Attaching a continuation with `then()` to a QFuture that has already finished, and then calling
`cancelChain()` on the resulting future, cancels the already-finished parent future; if the
parent's data has already been released this is a use-after-free. Separately, `unwrap()` on such
a future can hit the assertion "futureData already has a parent".

## 778111
`qUncompress()` on a tiny input (about 10 bytes) whose 4-byte big-endian size header claims
0xFFFFFFFF bytes makes Qt allocate about 4 GiB before it starts decompressing. Data with an
inaccurate size header must keep decompressing correctly.

## 771420
`QByteArray::repeated(n)` and `QString::repeated(n)` with a large `n`, such that `size() * n`
overflows, can write out of bounds instead of failing cleanly.

## 768692
`QUrl::toLocalFile()` fully decodes percent-encoding. For paths containing an encoded slash
(`%2F`, or `%5C` on Windows), an encoded NUL, or an invalid UTF-8 sequence it can return a local
path that means something different from the URL, which is unsafe for code that then opens the
file. Make `toLocalFile()` (and anything that relies on it) safe for such URLs.

## 769883
`QDate::fromString("2024-01-02 anything at all", Qt::ISODate)` returns a valid date and silently
ignores the trailing text. This is inconsistent with the corresponding QDateTime parsing.

## 772702
`QString::insert(qsizetype, QLatin1StringView)` does nothing when the view consists of a single
NUL character (e.g. `insert(0, "\0"_L1)`), and for an empty view it may read memory it should
not touch.

## 776166 (spare)
`QTimeZone::isValidId()` accepts ids where a component consists only of dots, such as `".."` or
`"Europe/../Paris"`.

## 769062 (spare)
`qUncompress()` can crash or show undefined behaviour on some corrupted inputs for which zlib
reports `Z_BUF_ERROR`.

# Feature tasks (frozen 2026-10-12, before any run)

## 768691
Add a private decode mode to QUrl's percent-decoding for local-file use. Name it
`QUrlDecodeForLocalFile` and declare it in `qurl_p.h` as a `QUrl::ComponentFormattingOptions`
value that already includes `QUrl::FullyDecoded`, so that
`qt_urlRecode(out, in, QUrlDecodeForLocalFile)` fully decodes. When called with this mode it
must fail — return a negative value — instead of producing a decoded string that would be
unsafe as a local file path: a decoded NUL or `/` (and `\` on Windows), or percent-encoded bytes
that are not valid UTF-8. Behaviour for every other mode stays the same. No existing caller has
to use the new mode yet.

## 756614
Add `void QThreadStorage<T>::clearLocalData()`, which resets the calling thread's local data, if
any, for both the pointer and the value variants of QThreadStorage. After the call
`hasLocalData()` is false. For pointer payloads this is already possible via
`setLocalData(nullptr)`; for value payloads it is not. Use the new function where it lets
existing Qt code use a value-based QThreadStorage instead of a workaround.

## 773405
Add to `QCborStreamReader` a `bool isNumber() const`, true when the current element is an
integer or an IEEE 754 floating-point value (half, single or double precision), and a
`double toNumber() const` that returns that value as a double whatever its CBOR numeric type.

## 777778
Add `static void QMimeDatabase::reload()`. QMimeDatabase re-reads changed MIME database files at
most every five seconds, so an application that installs a MIME type definition does not see it
for up to five seconds. After `reload()`, the next query must check the files at once, as when
the periodic check is due. Update existing tests that work around the delay to use the new
function.

<!-- Amendment 2026-10-13: 768691 spec originally said the value "combines with
QUrl::FullyDecoded"; the K0 rep-1 agent read that as "caller ORs it in", a legitimate reading
the maintainer test does not accept. Spec clarified; that run is excluded as a spec defect. -->

# Second batch — design-heavy tasks (frozen 2026-10-13, before any run)

## 764375
Calling `QThreadPool::clear()` while a `QtConcurrent::run()` task is still queued removes it
before it runs. Its QFuture then stays Running forever and `waitForFinished()` never returns.

## 765378
An application that still has a pending event whose destructor calls `deleteLater()` or
`postEvent()` deadlocks when it exits (seen with the Windows Media Foundation backend).

## 754389
ThreadSanitizer reports a data race when two connected QObjects that live in different threads
are destroyed in parallel: destroying the receiver calls into the sender while the sender may be
running its own destructors in its thread. QtNetwork triggers this on every HTTP request.

## 750871
`QObject::connect()` with member-function pointers is supposed to register the signal's
argument types with the meta-type system, so that queued connections and
`QMetaType::fromName()` work without `Q_DECLARE_METATYPE`. In Qt 6 it no longer does so for
types that are not declared with `Q_DECLARE_METATYPE`: Q_GADGET types, Q_ENUM types, pointers
and const pointers to QObject subclasses, and other complete types.

## 754345
`QXmlStreamReader::readElementText(QXmlStreamReader::IncludeChildElements)` crashes with a
stack overflow on input with very deeply nested elements.

## 759321
On some network file systems (observed on an NFSv4.2 server), removing or renaming a file that
still holds an active lock fails with `EBUSY`. As a result `QLockFile` on Unix can fail to
release its lock file, leaving a stale lock behind.
