"""Credential settings backed by QGIS's encrypted authentication database."""

import json

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
)

KEY = "rhinestone/credentials"


class CredentialError(ValueError):
    """A failure safe to display without credential values."""


class CredentialStore:
    def __init__(self, manager=None):
        self.manager = manager if manager is not None else QgsApplication.authManager()

    def unlock(self):
        if self.manager.isDisabled() or not self.manager.setMasterPassword():
            raise CredentialError("QGISの認証データベースを解除できません")

    def load(self):
        if not self.manager.existsAuthSetting(KEY):
            return {}
        self.unlock()
        try:
            values = json.loads(self.manager.authSetting(KEY, "", True))
        except (ValueError, TypeError) as error:
            raise CredentialError("保存した認証情報を読み取れません") from error
        if not isinstance(values, dict) or any(
            not isinstance(k, str) or not k or not isinstance(v, str) or not v
            for k, v in values.items()
        ):
            raise CredentialError("保存した認証情報の形式が不正です")
        return values

    def save(self, values):
        self.unlock()
        if values:
            success = self.manager.storeAuthSetting(
                KEY, json.dumps(values, ensure_ascii=False), True
            )
        else:
            success = not self.manager.existsAuthSetting(
                KEY
            ) or self.manager.removeAuthSetting(KEY)
        if not success:
            raise CredentialError("認証情報を保存・削除できません")


class SettingsDialog(QDialog):
    def __init__(self, parent=None, store=None):
        super().__init__(parent)
        self.store = store if store is not None else CredentialStore()
        self.values = self.store.load()
        self.setWindowTitle("Rhinestone 設定")
        self.setMinimumWidth(440)
        form = QFormLayout(self)
        note = QLabel(
            "認証情報はQGISの認証データベースへ暗号化保存します。\n"
            "国土交通DPFのAPIキーは名前を mlit-dpf としてください。\n"
            "登録しても未対応の認証方式・サービスは利用可能になりません。"
        )
        note.setWordWrap(True)
        form.addRow(note)
        self.name = QComboBox()
        self.name.setEditable(True)
        self.name.addItems(sorted(set(self.values) | {"mlit-dpf"}))
        self.secret = QLineEdit()
        self.secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.secret.setPlaceholderText("APIキー・トークン等。更新する値を入力")
        form.addRow("認証情報の名前", self.name)
        form.addRow("値", self.secret)
        self.state = QLabel()
        self.state.setWordWrap(True)
        self.state.setTextFormat(Qt.TextFormat.PlainText)
        form.addRow(self.state)
        self.save_button = QPushButton("保存・更新")
        self.delete_button = QPushButton("削除")
        close = QPushButton("閉じる")
        form.addRow(self.save_button, self.delete_button)
        form.addRow(close)
        self.name.currentTextChanged.connect(self.selected)
        self.save_button.clicked.connect(self.save_value)
        self.delete_button.clicked.connect(self.delete_value)
        close.clicked.connect(self.accept)
        self.selected()

    def selected(self, *_args):
        self.secret.clear()
        saved = self.name.currentText().strip() in self.values
        self.state.setText("登録済み（値は表示しません）" if saved else "未登録")
        self.delete_button.setEnabled(saved)

    def save_value(self):
        name, secret = self.name.currentText().strip(), self.secret.text()
        if not name or not secret:
            self.state.setText("名前と値を入力してください")
            return
        self.persist({**self.values, name: secret}, "保存しました")

    def delete_value(self):
        name = self.name.currentText().strip()
        self.persist(
            {k: v for k, v in self.values.items() if k != name}, "削除しました"
        )

    def persist(self, values, message):
        try:
            self.store.save(values)
        except CredentialError as error:
            self.state.setText(str(error))
            return
        self.values = values
        name = self.name.currentText().strip()
        if self.name.findText(name) < 0:
            self.name.addItem(name)
        self.selected()
        self.state.setText(message)

    def done(self, result):
        self.secret.clear()
        self.values.clear()
        super().done(result)
