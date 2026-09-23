package com.afudm.afutube.core.diagnostics

object SensitiveDataRedactor {
    private val secretHeader = Regex("(?im)^(\\s*(?:cookie|set-cookie|authorization|proxy-authorization)\\s*:\\s*).*$")
    private val secretQuery = Regex("(?i)([?&](?:token|access_token|auth_token|sig|signature|key|secret|oauth_token|api_key|query_token)=)[^&#\\s]+")
    private val inlineSecret = Regex("(?i)(\\b(?:cookie|authorization|token|sig|signature|key|secret)\\s*[=:]\\s*)[^\\s,;&?#]+")

    fun redact(value: String): String = value
        .replace(secretHeader, "$1<redacted>")
        .replace(secretQuery, "$1<redacted>")
        .replace(inlineSecret, "$1<redacted>")
}
