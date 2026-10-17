macro_rules! aria2_methods {
    () => {
        fn add_uri(&self, uris: &[String], options: Option<&JsonMap>) -> Result<String> {
            let value = self.invoke(
                "aria2.addUri",
                vec![json!(uris), json!(options.cloned().unwrap_or_default())],
            )?;
            serde_json::from_value(value)
                .map_err(|_| AfuError::Engine("beklenmeyen RPC yaniti".into()))
        }
        fn add_torrent(&self, torrent_b64: &str, options: Option<&JsonMap>) -> Result<String> {
            let value = self.invoke(
                "aria2.addTorrent",
                vec![
                    json!(torrent_b64),
                    json!([]),
                    json!(options.cloned().unwrap_or_default()),
                ],
            )?;
            serde_json::from_value(value)
                .map_err(|_| AfuError::Engine("beklenmeyen RPC yaniti".into()))
        }
        fn add_metalink(
            &self,
            metalink_b64: &str,
            options: Option<&JsonMap>,
        ) -> Result<Vec<String>> {
            let value = self.invoke(
                "aria2.addMetalink",
                vec![
                    json!(metalink_b64),
                    json!(options.cloned().unwrap_or_default()),
                ],
            )?;
            serde_json::from_value(value)
                .map_err(|_| AfuError::Engine("beklenmeyen RPC yaniti".into()))
        }
        fn pause(&self, gid: &str, force: bool) -> Result<String> {
            let value = self.invoke(
                if force {
                    "aria2.forcePause"
                } else {
                    "aria2.pause"
                },
                vec![json!(gid)],
            )?;
            serde_json::from_value(value)
                .map_err(|_| AfuError::Engine("beklenmeyen RPC yaniti".into()))
        }
        fn unpause(&self, gid: &str) -> Result<String> {
            let value = self.invoke("aria2.unpause", vec![json!(gid)])?;
            serde_json::from_value(value)
                .map_err(|_| AfuError::Engine("beklenmeyen RPC yaniti".into()))
        }
        fn remove(&self, gid: &str, force: bool) -> Result<String> {
            let value = self.invoke(
                if force {
                    "aria2.forceRemove"
                } else {
                    "aria2.remove"
                },
                vec![json!(gid)],
            )?;
            serde_json::from_value(value)
                .map_err(|_| AfuError::Engine("beklenmeyen RPC yaniti".into()))
        }
        fn remove_result(&self, gid: &str) -> Result<String> {
            let value = self.invoke("aria2.removeDownloadResult", vec![json!(gid)])?;
            serde_json::from_value(value)
                .map_err(|_| AfuError::Engine("beklenmeyen RPC yaniti".into()))
        }
        fn pause_all(&self) -> Result<String> {
            let value = self.invoke("aria2.pauseAll", vec![])?;
            serde_json::from_value(value)
                .map_err(|_| AfuError::Engine("beklenmeyen RPC yaniti".into()))
        }
        fn unpause_all(&self) -> Result<String> {
            let value = self.invoke("aria2.unpauseAll", vec![])?;
            serde_json::from_value(value)
                .map_err(|_| AfuError::Engine("beklenmeyen RPC yaniti".into()))
        }
        fn tell_status(&self, gid: &str, keys: &[&str]) -> Result<Json> {
            let value = self.invoke(
                "aria2.tellStatus",
                vec![json!(gid), json!(crate::rpc::status_keys(keys))],
            )?;
            serde_json::from_value(value)
                .map_err(|_| AfuError::Engine("beklenmeyen RPC yaniti".into()))
        }
        fn tell_active(&self, keys: &[&str]) -> Result<Vec<Json>> {
            let value = self.invoke(
                "aria2.tellActive",
                vec![json!(crate::rpc::status_keys(keys))],
            )?;
            serde_json::from_value(value)
                .map_err(|_| AfuError::Engine("beklenmeyen RPC yaniti".into()))
        }
        fn tell_waiting(&self, offset: i64, num: i64, keys: &[&str]) -> Result<Vec<Json>> {
            let value = self.invoke(
                "aria2.tellWaiting",
                vec![
                    json!(offset),
                    json!(num),
                    json!(crate::rpc::status_keys(keys)),
                ],
            )?;
            serde_json::from_value(value)
                .map_err(|_| AfuError::Engine("beklenmeyen RPC yaniti".into()))
        }
        fn tell_stopped(&self, offset: i64, num: i64, keys: &[&str]) -> Result<Vec<Json>> {
            let value = self.invoke(
                "aria2.tellStopped",
                vec![
                    json!(offset),
                    json!(num),
                    json!(crate::rpc::status_keys(keys)),
                ],
            )?;
            serde_json::from_value(value)
                .map_err(|_| AfuError::Engine("beklenmeyen RPC yaniti".into()))
        }
        fn global_stat(&self) -> Result<Json> {
            let value = self.invoke("aria2.getGlobalStat", vec![])?;
            serde_json::from_value(value)
                .map_err(|_| AfuError::Engine("beklenmeyen RPC yaniti".into()))
        }
        fn get_peers(&self, gid: &str) -> Result<Vec<Json>> {
            let value = self.invoke("aria2.getPeers", vec![json!(gid)])?;
            serde_json::from_value(value)
                .map_err(|_| AfuError::Engine("beklenmeyen RPC yaniti".into()))
        }
        fn get_files(&self, gid: &str) -> Result<Vec<Json>> {
            let value = self.invoke("aria2.getFiles", vec![json!(gid)])?;
            serde_json::from_value(value)
                .map_err(|_| AfuError::Engine("beklenmeyen RPC yaniti".into()))
        }
        fn get_servers(&self, gid: &str) -> Result<Vec<Json>> {
            let value = self.invoke("aria2.getServers", vec![json!(gid)])?;
            serde_json::from_value(value)
                .map_err(|_| AfuError::Engine("beklenmeyen RPC yaniti".into()))
        }
        fn change_option(&self, gid: &str, options: &JsonMap) -> Result<String> {
            let value = self.invoke("aria2.changeOption", vec![json!(gid), json!(options)])?;
            serde_json::from_value(value)
                .map_err(|_| AfuError::Engine("beklenmeyen RPC yaniti".into()))
        }
        fn change_global_option(&self, options: &JsonMap) -> Result<String> {
            let value = self.invoke("aria2.changeGlobalOption", vec![json!(options)])?;
            serde_json::from_value(value)
                .map_err(|_| AfuError::Engine("beklenmeyen RPC yaniti".into()))
        }
        fn change_uri(
            &self,
            gid: &str,
            file_index: i64,
            del_uris: &[String],
            add_uris: &[String],
            position: i64,
        ) -> Result<i64> {
            let value = self.invoke(
                "aria2.changeUri",
                vec![
                    json!(gid),
                    json!(file_index),
                    json!(del_uris),
                    json!(add_uris),
                    json!(position),
                ],
            )?;
            serde_json::from_value(value)
                .map_err(|_| AfuError::Engine("beklenmeyen RPC yaniti".into()))
        }
        fn get_global_option(&self) -> Result<JsonMap> {
            let value = self.invoke("aria2.getGlobalOption", vec![])?;
            serde_json::from_value(value)
                .map_err(|_| AfuError::Engine("beklenmeyen RPC yaniti".into()))
        }
        fn shutdown(&self, force: bool) -> Result<String> {
            let value = self.invoke(
                if force {
                    "aria2.forceShutdown"
                } else {
                    "aria2.shutdown"
                },
                vec![],
            )?;
            serde_json::from_value(value)
                .map_err(|_| AfuError::Engine("beklenmeyen RPC yaniti".into()))
        }
        fn save_session(&self) -> Result<String> {
            let value = self.invoke("aria2.saveSession", vec![])?;
            serde_json::from_value(value)
                .map_err(|_| AfuError::Engine("beklenmeyen RPC yaniti".into()))
        }
    };
}
