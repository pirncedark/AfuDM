package com.afudm.afutube.downloader

/** Dependency-free JVM checks; main can be run without Android or JUnit. */
object TorrentWorkerTest {
    @JvmStatic
    fun main(args: Array<String>) {
        val progress = checkNotNull(parseTorrentProgress(
            "[#abcd12 12MiB/100MiB(12%) CN:5 DL:2.1MiB ETA:1m]"))
        check(progress == TorrentProgress(12, "12MiB/100MiB", "2.1MiB/s", 60, false))
        check(parseTorrentProgress("unrelated notice") == null)
        check(parseTorrentProgress("[#abc 1GiB/2GiB(50%) CN:2 DL:0B ETA:1d2h3m4s]")?.etaSeconds == 93784L)
        check(parseTorrentProgress("[#abc 0B/0B CN:0 DL:0B]")?.totalUnknown == true)
        check(parseTorrentProgress("[#abc 10MiB/10MiB(100%) CN:1]")?.percent == 100)
        check(parseTorrentProgress("[#abc 1MiB/2MiB(150%) DL:1MiB]")?.percent == 100)
        check(parseTorrentProgress("[#abc 1MiB/2MiB(50%) CN:1]")?.speed == "")
        check(parseTorrentProgress("[#abc 1MiB/2MiB(50%) CN:1]")?.etaSeconds == 0L)
        val magnet = "magnet:?xt=urn:btih:abc&dn=some name"
        val commands = torrentArguments("/native/libaria2c.so", "/downloads/a b", magnet)
        check(commands.first() == "/native/libaria2c.so")
        check(commands.last() == magnet)
        check("--dir=/downloads/a b" in commands)
        check("--seed-time=0" in commands && "--follow-torrent=true" in commands)
        check("--bt-save-metadata=true" in commands && "--continue=true" in commands)
        check(torrentArguments("/native/libaria2c.so", "/downloads", "/cache/a b.torrent").last() == "/cache/a b.torrent")
        check(runCatching { torrentArguments("aria2c", "/downloads", "--bad") }.isFailure)
        check("--ca-certificate=/cert/a b.pem" in torrentArguments("aria2c", "/out", magnet, "/cert/a b.pem"))
        println("TorrentWorkerTest: 16 checks passed")
    }
}
