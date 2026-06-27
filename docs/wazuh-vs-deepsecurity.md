# Wazuh と Trend Micro Deep Security 機能対比ドキュメント

## 概要

本ドキュメントは、OSSのHIDS「Wazuh」と商用製品「Trend Micro Deep Security（DS）」の機能対比をまとめたものです。  
Wazuhで同等機能を実装し、機能差異を整理しています。

---

## 1. 機能対比表

| Deep Security モジュール | Wazuh の対応機能 | 実装状況 | 備考 |
|---|---|---|---|
| **変更監視（Integrity Monitoring）** | **FIM（File Integrity Monitoring）** | ✅ 実装済み | `/etc`, `/opt/app` を監視。リアルタイム検知済み |
| **セキュリティログ監視（Log Inspection）** | **Log Data Collection + Decoders** | ✅ 実装済み | journald 経由でシステムログを収集 |
| **侵入防御（IPS/IDS）** | **Wazuh ルールエンジン + Active Response** | ✅ 設定済み | SSH brute force 検知→自動ブロック（rule 5712） |
| **不正プログラム対策（Anti-Malware）** | **VirusTotal 統合 / ClamAV 連携** | 🔲 未実装 | DSのリアルタイムスキャンに相当。追加設定で対応可 |
| **脆弱性管理（Vulnerability Shielding）** | **Vulnerability Detector** | 🔲 設定済み（スキャン待ち） | NVD/CVEデータベースと連携してCVEスキャン |
| **Webアプリケーション保護（WAF）** | **Nginx + ModSecurity（別途）** | 🔲 未実装 | DSのDeep Packet Inspectionに相当 |
| **アプリケーションコントロール** | **Wazuh SCA（Security Configuration Assessment）** | ✅ 動作中 | ホストのセキュリティ設定を自動監査 |
| **ファイアウォール** | **AWS Security Group + iptables** | ✅ 実装済み | インバウンド制限をSGで管理 |

---

## 2. 各機能の詳細比較

### 2-1. 変更監視 / FIM

| 項目 | Deep Security | Wazuh |
|---|---|---|
| 監視方式 | エージェントベース、カーネルドライバ | エージェントベース、inotify |
| リアルタイム検知 | ✅ | ✅（`realtime="yes"` 設定） |
| 監視対象 | ファイル・レジストリ・プロセス・ポート | ファイル・ディレクトリ |
| ベースライン管理 | 自動取得 | 初回スキャン時に自動取得 |
| MITRE ATT&CK マッピング | ✅ | ✅（T1070.004, T1485 など自動分類） |
| 実装例 | DSポリシーで監視パスを指定 | `ossec.conf` の `<syscheck>` セクションで設定 |

**本環境での設定（ossec.conf）:**
```xml
<syscheck>
  <frequency>300</frequency>
  <directories check_all="yes" realtime="yes">/etc</directories>
  <directories check_all="yes" realtime="yes">/opt/app</directories>
</syscheck>
```

**検知実績:**
- `/etc/wazuh-fim-test.txt` の作成・削除を即時検知
- MITRE ATT&CK T1070.004（Defense Evasion）・T1485（Impact）に自動分類

---

### 2-2. セキュリティログ監視 / Log Inspection

| 項目 | Deep Security | Wazuh |
|---|---|---|
| 対応ログ形式 | syslog, Windows Event Log, Apache, etc. | syslog, journald, JSON, Apache, etc. |
| ルールエンジン | DSのLog Inspection Rules（XML） | Wazuh Decoder + Rules（XML） |
| 相関分析 | ✅ | ✅ |
| アラートレベル | 重要度 1〜15 | レベル 0〜15 |
| カスタムルール | ✅ | ✅ |

**本環境での設定:**
- journald 経由でシステムイベントを収集
- `Rule 510`（rootcheck）、`Rule 533`（ポート変更）などを検知済み

---

### 2-3. 侵入防御 / IPS

| 項目 | Deep Security | Wazuh |
|---|---|---|
| 方式 | ネットワークベースDPI（Deep Packet Inspection） | ホストベース（ルールマッチング） |
| シグネチャ更新 | Trend Micro Smart Protection Network | Wazuh ルールセット（コミュニティ） |
| 自動ブロック | ✅ | ✅（Active Response） |
| SSH brute force 対応 | ✅ | ✅（rule 5712 → firewall-drop） |

**本環境でのActive Response設定:**
```xml
<active-response>
  <command>firewall-drop</command>
  <location>local</location>
  <rules_id>5712</rules_id>
  <timeout>180</timeout>
</active-response>
```

---

### 2-4. 脆弱性管理

| 項目 | Deep Security | Wazuh |
|---|---|---|
| CVEスキャン | ✅ 自動 | ✅（Vulnerability Detector） |
| データソース | Trend Micro Threat Intelligence | NVD（National Vulnerability Database） |
| パッチ適用 | ✅ 連携可 | 🔲（検知のみ） |
| スキャン頻度 | リアルタイム〜定期 | 定期（設定可） |

---

## 3. アーキテクチャ比較

### Deep Security の一般的な構成
```
[DS Manager（管理サーバ）]
        ↓ ポリシー配布
[DS Agent（各サーバ）] → 検知・ブロック → [DS Manager] → [SIEMへ転送]
```

### 本環境の Wazuh 構成
```
[Wazuh Manager + Dashboard（EC2: 13.115.74.134）]
        ↓ 設定配布
[Wazuh Manager 自身（Agent ID: 000）] → 検知 → [Wazuh Indexer] → [Wazuh Dashboard]
```

---

## 4. 運用面の比較

| 項目 | Deep Security | Wazuh |
|---|---|---|
| コスト | 商用ライセンス（高額） | OSS（無料） |
| サポート | Trend Micro 公式サポート | コミュニティ + 有償サポートあり |
| セットアップ難易度 | 中（GUIベース） | 中〜高（設定ファイルベース） |
| スケーラビリティ | ✅ 大規模環境向け | ✅（クラスタ構成可） |
| クラウド対応 | ✅ DSaaS | ✅（AWS/Azure/GCP対応） |
| SIEM連携 | ✅ | ✅（Elastic Stack, Splunk等） |
| コンプライアンス対応 | PCI DSS, HIPAA, GDPR | PCI DSS, HIPAA, GDPR, NIST |

---

## 5. DS 初期設定タスクとの対応マッピング

| DS 初期設定タスク | Wazuh での実装内容 |
|---|---|
| エージェントインストール | Wazuh all-in-one インストール・Manager 起動 |
| ポリシー作成（変更監視） | ossec.conf の syscheck 設定（監視パス・頻度・リアルタイム） |
| ポリシー作成（ログ監視） | localfile 設定 / journald 連携 |
| アラートチューニング | Wazuh ルールレベル調整・誤検知低減 |
| ダッシュボード確認 | Wazuh Dashboard（MITRE ATT&CK ビュー・アラート確認） |
| インシデント対応 | Active Response 設定（自動ブロック・対応フロー） |
| レポート作成 | Wazuh PDF レポート生成・エビデンス管理 |

---

## 6. Deep Security の優位点

DSが優れている点:

1. **カーネルレベルの保護**: DSのドライバはOSコア部分で動作し、Wazuhより深い保護が可能
2. **リアルタイム脆弱性防御（Virtual Patching）**: パッチ未適用でも脆弱性を仮想的に封鎖
3. **Trend Micro の脅威インテリジェンス**: 世界規模の攻撃情報をリアルタイムで反映
4. **統合管理**: 1つのコンソールでAV・FW・IPS・FIM・ログ監視を統合管理
5. **サポート体制**: 24/7 の公式サポートで本番環境でも安心

---

## 7. まとめ

OSSのWazuhを用いて以下を実装・検証しました：

- FIM・ログ監視・異常検知・自動対応の設定と運用
- MITRE ATT&CK フレームワークへの実践的な理解
- Wazuh と Deep Security の機能差異の整理・文書化

DS固有の機能（Virtual Patching、Trend Micro TI連携など）はDS環境での習得が別途必要ですが、HISDの概念・設定手順・運用フローはWazuhで実装済みです。
