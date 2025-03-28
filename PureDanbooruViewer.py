import sys
import os
import webbrowser
import configparser
import polars as pl
import i18n
import tarfile
import base64
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, pyqtSignal, QEvent, QTimer, QByteArray
from PyQt5.QtGui import QIntValidator, QPixmap, QValidator, QIcon

# グローバル変数
tar_cache = {} # tarオブジェクトのキャッシュ
result_cache = {} # グローバルキャッシュ
config = now_lang = None
app = None  # PyQt5 アプリケーションインスタンス

# PureDanbooruとかのあれこれ
purebooru = parquet_dir = idx_dir = ''
idx_alpha = idx_dupli = idx_image = ''
dan_post = dan_rels = dan_tags = None
gel_post = gel_rels = gel_tags = None
img_dan = img_gel = img_alp = img_dup_dan = img_dup_gel = ''
tag_search_limit = 1000
no_tar = parquet_only = noAlpha = False
replace_underscore = hide_megatags = escape_brancket = True

pol_dan_post = pol_dan_rels = pol_dan_tags = None
pol_gel_post = pol_gel_rels = pol_gel_tags = None

last_save_path = os.path.dirname(__file__)
#icons = []

# メインウィンドウclass
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        # アイコンの設定
        #self.get_icon()
        #self.setWindowIcon(icons[0])
        
        # レイアウト
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)

        # 設定ファイルの読み込み
        self.readINI()
        
        # メニューバーの作成
        mainmenu = QMenuBar()

        # メニューの作成
        option_menu = mainmenu.addMenu('File') 
        
        # メニューアイテム(アクション)の作成
        save_action = QAction('Save Config', self)
        save_action.setShortcut(Qt.Key.Key_S + Qt.KeyboardModifier.ControlModifier)
        save_action.triggered.connect(lambda: self.saveINI())

        option_action = QAction('Option', self)
        option_action.setShortcut(Qt.Key.Key_F1)
        option_action.triggered.connect(lambda: self.option_button_clicked(title='Option', isInit=False))
        
        exit_action = QAction('Exit', self)
        exit_action.triggered.connect(self.close)

        # メニューにメニューアイテムを追加
        option_menu.addAction(save_action)
        option_menu.addAction(option_action)
        option_menu.addAction(exit_action)

        # langメニューの追加
        lang_menu = mainmenu.addMenu('Lang')
        langs = self.get_langlist()
        self.lang_action = {}
        for l in langs:
            self.lang_action[l] = QAction(l, self)
            self.lang_action[l].setCheckable(True)
            self.lang_action[l].triggered.connect(lambda checked, lang=l: self.menu_lang_changed(lang))
            lang_menu.addAction(self.lang_action[l])
        self.lang_action[now_lang].setChecked(True)
        
        main_layout.setMenuBar(mainmenu)

        self.setWindowTitle('Pure-Danbooru Viewer')
        self.setGeometry(config.getint('MAIN', 'x', fallback=100),
                         config.getint('MAIN', 'y', fallback=100),
                         config.getint('MAIN', 'width', fallback=300),
                         config.getint('MAIN', 'height', fallback=500))
        self.setMinimumSize(300, 500)

        # 検索件数制限
        limit_frame = QWidget()
        limit_layout = QHBoxLayout()
        limit_layout.setSpacing(0)
        limit_layout.setContentsMargins(5,1,5,1)
        limit_frame.setLayout(limit_layout)
        limit_label = QLabel('Limit Results ')
        limit_label.setFixedWidth(70)
        limit_layout.addWidget(limit_label)
        self.limit_entry = CustomLineEdit(config.get('MAIN', 'limit_entry', fallback='1000'))
        self.limit_entry.setValidator(QIntValidator(1, 1000000, self))
        limit_layout.addWidget(self.limit_entry)
        
        # データソース設定
        sql_frame = QWidget()
        sql_layout = QHBoxLayout()
        sql_layout.setSpacing(0)
        sql_layout.setContentsMargins(5,1,5,1)
        sql_frame.setLayout(sql_layout)
        sql_source = QLabel(' Data Source ')
        sql_source.setFixedWidth(70)
        sql_layout.addWidget(sql_source)
        self.sql_combobox = QComboBox()
        self.sql_combobox.addItems(['Danbooru', 'Gelbooru'])
        self.sql_combobox.setCurrentText(config.get('MAIN', 'sql_combobox', fallback='Danbooru'))
        self.sql_combobox.setEditable(False)
        self.sql_combobox.currentIndexChanged.connect(lambda: self.on_sql_source_changed())
        sql_layout.addWidget(self.sql_combobox)
        
        # タグ入力ボックス
        search_frame = QWidget()
        self.search_layout = QVBoxLayout()
        self.search_layout.setSpacing(2)
        self.search_layout.setContentsMargins(5,1,5,1)
        search_frame.setLayout(self.search_layout)
        self.search_entries = []
        self.add_search_box(isInit=True)  # 初期検索ボックスを追加
        self.last_count = 0 # 検索処理を一部簡素化するための値
        
        # 検索実行ボタン
        exec_frame = QWidget()
        exec_layout = QHBoxLayout()
        exec_layout.setSpacing(0)
        exec_layout.setContentsMargins(5,1,5,1)
        exec_frame.setLayout(exec_layout)
        self.exec_button = QPushButton('Search')
        self.exec_button.clicked.connect(lambda: self.search_data())
        exec_layout.addWidget(self.exec_button)

        # 初期化ボタン
        init_frame = QWidget()
        init_layout = QHBoxLayout()
        init_layout.setSpacing(0)
        init_layout.setContentsMargins(5,1,5,1)
        init_frame.setLayout(init_layout)
        init_button = QPushButton('Clear Tags')
        init_button.clicked.connect(lambda: self.clear_tags())
        init_layout.addWidget(init_button)

        # タグビューワー表示ボタン
        tag_view_frame = QWidget()
        tag_view_layout = QHBoxLayout()
        tag_view_layout.setSpacing(0)
        tag_view_layout.setContentsMargins(5,1,5,1)
        tag_view_frame.setLayout(tag_view_layout)
        tag_view_button = QPushButton('Tag Viewer')
        tag_view_button.clicked.connect(lambda: self.tag_view_button_clicked(isInit=False))
        tag_view_layout.addWidget(tag_view_button)
        
        # ID直指定
        post_order_frame = QWidget()
        post_order_layout = QHBoxLayout()
        post_order_layout.setSpacing(0)
        post_order_layout.setContentsMargins(5,1,5,1)
        post_order_frame.setLayout(post_order_layout)
        post_order_lbl = QLabel('      Post ID ')
        post_order_lbl.setFixedWidth(70)
        post_order_layout.addWidget(post_order_lbl, alignment=Qt.AlignVCenter | Qt.AlignRight)
        self.post_order_input = CustomLineEdit('')
        self.post_order_input.setValidator(Uint32Validator(minimum=1))
        self.post_order_input.returnPressed.connect(lambda: self.post_order_button_clicked())
        post_order_layout.addWidget(self.post_order_input)
        post_order_button = QPushButton('\U0001F50E')
        post_order_button.setFixedWidth(30)
        post_order_button.clicked.connect(lambda: self.post_order_button_clicked())
        post_order_layout.addWidget(post_order_button)

        main_layout.addWidget(limit_frame)
        main_layout.addWidget(sql_frame)
        main_layout.addWidget(search_frame)
        main_layout.addWidget(exec_frame)
        main_layout.addSpacing(15)
        main_layout.addWidget(init_frame)
        main_layout.addWidget(tag_view_frame)
        main_layout.addStretch()
        main_layout.addWidget(post_order_frame)
        
        # ... (各種イベントハンドラの実装)
        self.search_entries[0][1].setFocus()

        # result_windowの初期起動
        df = pl.DataFrame()
        self.show_results(dataframe=df, cache_key=None)
        self.tag_view_button_clicked(isInit=True)
    
    ########## 起動/終了処理関連 ##########
    # ベースParquet存在チェック
    def chkBaseParquet(self, tmppath):
        # パス設定
        dp = os.path.join(tmppath, 'dan_post.parquet')
        dr = os.path.join(tmppath, 'dan_rels.parquet')
        dt = os.path.join(tmppath, 'dan_tags.parquet')
        gp = os.path.join(tmppath, 'gel_post.parquet')
        gr = os.path.join(tmppath, 'gel_rels.parquet')
        gt = os.path.join(tmppath, 'gel_tags.parquet')

        chkPar = []
        chkPar.append('dan_post') if not os.path.exists(dp) else None
        chkPar.append('dan_rels') if not os.path.exists(dr) else None
        chkPar.append('dan_tags') if not os.path.exists(dt) else None
        chkPar.append('gel_post') if not os.path.exists(gp) else None
        chkPar.append('gel_rels') if not os.path.exists(gr) else None
        chkPar.append('gel_tags') if not os.path.exists(gt) else None
        
        if len(chkPar) > 0:
            return False
            
        return True

    # PureDanbooru存在チェック
    def chkPureDanbooru(self, tmppath):
        chkdir = []
        chkdir.append('alphachannel')    if not os.path.exists(os.path.join(tmppath, 'alphachannel')) else None
        chkdir.append('duplicate_image') if not os.path.exists(os.path.join(tmppath, 'duplicate_image')) else None
        chkdir.append('image')           if not os.path.exists(os.path.join(tmppath, 'image')) else None
        #chkdir.append('metadata')        if not os.path.exists(os.path.join(tmppath, 'metadata')) else None
        
        if len(chkdir) > 0:
            return False

        return True

    # TarIndex用Parquet存在チェック
    def chkTarIndexParquet(self, tmppath):
        # パス設定
        ia = os.path.join(tmppath, 'tarIndex_alphachannel.parquet')
        id = os.path.join(tmppath, 'tarIndex_duplicate.parquet')
        ii = os.path.join(tmppath, 'tarIndex_image.parquet')
        #im = os.path.join(tmppath, 'tarIndex_metadata.parquet')

        chkPar = []
        chkPar.append('idx_alpha') if not os.path.exists(ia) else None
        chkPar.append('idx_dupli') if not os.path.exists(id) else None
        chkPar.append('idx_image') if not os.path.exists(ii) else None
        #chkPar.append('idx_meta') if not os.path.exists(im) else None
        
        if len(chkPar) > 0:
            return False
            
        return True

    # 設定ファイルの読み込み
    def readINI(self):
        global config, now_lang
        global parquet_dir, no_tar, parquet_only, noAlpha
        global dan_post, dan_rels, dan_tags, gel_post, gel_rels, gel_tags
        global purebooru
        global idx_dir, idx_alpha, idx_dupli, idx_image #, idx_meta
        global img_dan, img_gel, img_alp, img_dup_dan, img_dup_gel
        global replace_underscore, hide_megatags, escape_brancket
        global tag_search_limit
        global pol_dan_post, pol_dan_rels, pol_dan_tags
        global pol_gel_post, pol_gel_rels, pol_gel_tags
        
        # 設定ファイルの読み込み
        config = configparser.ConfigParser()
        config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
        config.read(config_path, encoding='utf-8')

        # 言語ファイルの読み込み
        try:
            os.makedirs(os.path.join(os.path.dirname(__file__), 'lang'), exist_ok=True)
            i18n.load_path.append(os.path.join(os.path.dirname(__file__), 'lang'))
            # 言語ファイルの存在確認
            now_lang = config.get('DEFAULT', 'lang', fallback='en')
            lang_file = f"lang.{now_lang}.yml"
            lang_exists = os.path.exists(os.path.join(os.path.dirname(__file__), 'lang', lang_file))
            if not lang_exists:
                # 指定した言語ファイルが存在しない場合
                # ちょっとお行儀悪いけどlangたちをenにして使いまわし再チェック
                now_lang = 'en'
                lang_exists = lang_file = f"lang.{now_lang}.yml"
                lang_exists = os.path.exists(os.path.join(os.path.dirname(__file__), 'lang', lang_file))
                if not lang_exists:
                    # enもないなら作成してセットする
                    self.lang_file_missing()
            i18n.set('locale', now_lang) # 初期設定は英語？にする
        except Exception as e:
            # 多分起きないと思うけど念のため
            print(f'Exception: {e}')
            self.lang_file_missing()

        # コンフィグファイルから値を取得
        parquet_dir = config.get('DEFAULT', 'parquet_dir', fallback='./parquet')
        
        no_tar = config.getboolean('DEFAULT', 'no_tar', fallback=False)
        parquet_only = config.getboolean('DEFAULT', 'parquet_only', fallback=False)
        noAlpha = config.getboolean('DEFAULT', 'noAlpha', fallback=True)
        
        purebooru = config.get('DEFAULT', 'purebooru', fallback='./PuraDanbooru')
        idx_dir = config.get('DEFAULT', 'idx_dir', fallback='./parquet')

        img_dan = config.get('DEFAULT', 'img_dan', fallback='./image/Danbooru/extract')
        img_gel = config.get('DEFAULT', 'img_gel', fallback='./image/Gelbooru/extract')
        img_alp = config.get('DEFAULT', 'img_alp', fallback='./alphachannel/extract')
        img_dup_dan = config.get('DEFAULT', 'img_dup_dan', fallback='./duplicate_image/Danbooru/extract')
        img_dup_gel = config.get('DEFAULT', 'img_dup_gel', fallback='./duplicate_image/Gelbooru/extract')
        
        replace_underscore = config.getboolean('OPTION', 'replace_underscore', fallback=True)
        hide_megatags = config.getboolean('OPTION', 'hide_megatags', fallback=True)
        escape_brancket = config.getboolean('OPTION', 'escape_brancket', fallback=True)

        tag_search_limit = config.get('TAG_VIEW', 'limit_tags', fallback='1000')

        # セクションがない場合の追加処理
        sections = ['MAIN', 'RESULT', 'TAG_VIEW', 'OPTION', 'PREVIEW']
        for section in sections:
            if not config.has_section(section):
                config.add_section(section)

        chk = True
        if not parquet_only: # ベースparquetだけでいい人はtar関連を確認しない
            if not no_tar: # no_tarがFalseなら
                chk = chk and self.chkPureDanbooru(tmppath=purebooru) # PureDanbooruフォルダの確認
                chk = chk and self.chkTarIndexParquet(tmppath=idx_dir) # tarIndex Parquetの確認
        
        # ベースparquetの確認
        chk = chk and self.chkBaseParquet(tmppath=parquet_dir)

        if not chk:
            # 初回起動、あるいは存在確認チェックでエラーが出たらオプション画面を表示
            title = 'Read Config Error'
            #msg = 'Some files or folders are not found.\nEnter the initial settings.'
            msg = self.escape_i18n_newline(key='lang.config_load_err')
            
            # 初回起動等でコンフィグファイルがない時はタイトルとかちょっと変える
            if not os.path.exists(os.path.join(os.path.dirname(__file__), 'config.ini')):
                title = 'Hello!'
                #msg = 'ConfigFile not found.\nEnter the initial settings.'
                msg = self.escape_i18n_newline(key='lang.config_missing_err')
            # 初回起動ifここまで

            res = QMessageBox.information(self, title, msg, QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
            if res == QMessageBox.StandardButton.Cancel:
                sys.exit()
                return
            
            # 初回起動用オプション画面を表示
            wait = self.option_button_clicked(title='Initial settings', isInit=True)
            if not wait:
                sys.exit()
                return
            
        # Base Parquetのパス設定
        dan_post = os.path.abspath(os.path.join(parquet_dir, 'dan_post.parquet'))
        dan_rels = os.path.abspath(os.path.join(parquet_dir, 'dan_rels.parquet'))
        dan_tags = os.path.abspath(os.path.join(parquet_dir, 'dan_tags.parquet'))
        gel_post = os.path.abspath(os.path.join(parquet_dir, 'gel_post.parquet'))
        gel_rels = os.path.abspath(os.path.join(parquet_dir, 'gel_rels.parquet'))
        gel_tags = os.path.abspath(os.path.join(parquet_dir, 'gel_tags.parquet'))

        # Parquetをメモリに載せる
        pol_dan_post = pl.scan_parquet(dan_post)
        pol_gel_post = pl.scan_parquet(gel_post)
        pol_dan_rels = pl.scan_parquet(dan_rels)
        pol_gel_rels = pl.scan_parquet(gel_rels)
        pol_dan_tags = pl.scan_parquet(dan_tags)
        pol_gel_tags = pl.scan_parquet(gel_tags)

        # Tar Indexのパス設定
        idx_alpha = os.path.abspath(os.path.join(idx_dir, 'tarIndex_alphachannel.parquet'))
        idx_dupli = os.path.abspath(os.path.join(idx_dir, 'tarIndex_duplicate.parquet'))
        idx_image = os.path.abspath(os.path.join(idx_dir, 'tarIndex_image.parquet'))
        #idx_meta = os.path.abspath(os.path.join(idx_dir, 'tarIndex_metadata.parquet'))

    # 設定ファイルの保存
    def saveINI(self):
        global config, now_lang, purebooru
        global parquet_dir, idx_dir
        global img_dan, img_gel, img_alp, img_dup_dan, img_dup_gel
        global no_tar, parquet_only, noAlpha
        global replace_underscore, hide_megatags, escape_brancket

        config.set('DEFAULT', 'lang', now_lang)

        config.set('DEFAULT', 'parquet_dir', parquet_dir)

        config.set('DEFAULT', 'no_tar', str(no_tar))
        config.set('DEFAULT', 'parquet_only', str(parquet_only))
        config.set('DEFAULT', 'noAlpha', str(noAlpha))
        config.set('DEFAULT', 'purebooru', purebooru)
        config.set('DEFAULT', 'idx_dir', idx_dir)

        config.set('DEFAULT', 'img_dan', img_dan)
        config.set('DEFAULT', 'img_gel', img_gel)
        config.set('DEFAULT', 'img_alp', img_alp)
        config.set('DEFAULT', 'img_dup_dan', img_dup_dan)
        config.set('DEFAULT', 'img_dup_gel', img_dup_gel)

        if hasattr(self, 'limit_entry'):
            config.set('MAIN', 'x', str(self.geometry().x()))
            config.set('MAIN', 'y', str(self.geometry().y()))
            config.set('MAIN', 'width', str(self.width()))
            config.set('MAIN', 'height', str(self.height()))
            config.set('MAIN', 'limit_entry', self.limit_entry.text().strip())
            config.set('MAIN', 'sql_combobox', self.sql_combobox.currentText().strip())

        if hasattr(self, 'result_window'):
            config.set('RESULT', 'x', str(self.result_window.geometry().x()))
            config.set('RESULT', 'y', str(self.result_window.geometry().y()))
            config.set('RESULT', 'width', str(self.result_window.width()))
            config.set('RESULT', 'height', str(self.result_window.height()))
            config.set('RESULT', 'save_with', self.save_with_result.currentText().strip())
            config.set('RESULT', 'auto_preview', str(self.auto_preview.isChecked()))

        if hasattr(self, 'preview_window') and self.preview_window.isVisible():
            config.set('PREVIEW', 'x', str(self.preview_window.geometry().x()))
            config.set('PREVIEW', 'y', str(self.preview_window.geometry().y()))
            config.set('PREVIEW', 'width', str(self.preview_window.width()))
            config.set('PREVIEW', 'height', str(self.preview_window.height()))
            config.set('PREVIEW', 'save_with', self.save_with_preview.currentText().strip())
        
        if hasattr(self, 'tag_window') and self.tag_window.isVisible():
            config.set('TAG_VIEW', 'x', str(self.tag_window.geometry().x()))
            config.set('TAG_VIEW', 'y', str(self.tag_window.geometry().y()))
            config.set('TAG_VIEW', 'width', str(self.tag_window.width()))
            config.set('TAG_VIEW', 'height', str(self.tag_window.height()))
            config.set('TAG_VIEW', 'limit_tags', self.tag_search_limit.text().strip())

        if hasattr(self, 'option_window') and self.option_window.isVisible():
            config.set('OPTION', 'x', str(self.option_window.geometry().x()))
            config.set('OPTION', 'y', str(self.option_window.geometry().y()))
            config.set('OPTION', 'width', str(self.option_window.width()))
            config.set('OPTION', 'height', str(self.option_window.height()))
            config.set('OPTION', 'replace_underscore', str(self.op_tss_replace_underscore.isChecked()))
            config.set('OPTION', 'hide_megatags', str(self.op_tss_hide_megatags.isChecked()))
            config.set('OPTION', 'escape_brancket', str(self.op_tss_escape_brancket.isChecked()))
            
        config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
        with open(config_path, 'w') as configfile:
            config.write(configfile)

    # 初期言語ファイルの再生成
    def lang_file_missing(self):
        # 言語ファイルがなかった場合、jpとenを作って保存して再セット
        ja = """ja:
  ##### 起動時のコンフィグ関連
  # コンフィグファイル中のフォルダ等参照エラー
  config_load_err: 'いくつかのファイルまたはフォルダが見つかりませんでした。\\n初期設定画面に入ります。'

  # コンフィグファイルが存在しない
  config_missing_err: '設定ファイルが存在しません。\\n初期設定画面に入ります。'

  ##### オプション画面
  # no_tarオプション
  opt_no_tar_lbl: 'tarファイルを使用しない'

  # no_Alphaオプション
  opt_no_alpha_lbl: 'alphachannel画像を読み込まない'

  # Parquet Onlyオプション
  opt_parquet_only_lbl: 'Parquetファイルだけで動作させる'

  # PureDanbooruパス
  opt_puredanbooru_root: 'Pure-Danbooru root'

  # tarインデックスParquetパス
  opt_tarindex_parquet_lbl: 'tarIndex Parquetフォルダ'

  # Replace Underscore
  opt_replace_underscore_lbl: 'アンダーバーを空白に置換する'

  # Hide Metatags
  opt_hide_metatags_lbl: 'メタタグを非表示にする'

  # Escape Curvy Brancket
  opt_escape_curvy_brancket_lbl: '()を\(\)に置換する'

  # オプション画面、ベースParquetフォルダ選択ボタン(parquet存在チェック)
  opt_base_parquet_exists_err: 'Parquetファイルが見つかりません。\\nフォルダを選択しなおしてください'

  # オプション画面、PureDanbooruフォルダ選択ボタン(サブフォルダ存在チェック)
  opt_puredanbooru_exists_err: '選択したフォルダが誤っているようです。\\nフォルダを選択しなおしてください'

  # オプション画面、TarIndex Parquetフォルダ選択ボタン
  opt_tarindex_exists_err: 'tarファイル用のParquetファイルが見つかりません。\\nフォルダを選択しなおしてください'

  # オプション画面、保存ボタン(ベースParquet存在確認)
  opt_need_base_parquet_err: 'このプログラムはベースParquetファイルがないと正常に動作しません。\\nフォルダを選択しなおしてください'

  # オプション画面、キャンセルボタン(値の変更を検知)
  opt_cancel_caution: 'いくつかの設定が変更されているようです。変更を適用しますか？'

  ##### 検索実行
  # 検索実行 - 0件エラー
  search_0_err: '入力されたタグに一致するデータが存在しません'

  ##### result_window関連
  # result_windowからのデータ保存 no_tarチェック警告
  result_use_tar_warning: 'tarファイルを利用するモードを選択中です。\\n画像保存に時間がかかることが予想されますが続けますか？'

  # result_windowからのデータ保存 警告文ありの終了メッセージ
  save_finished_with_err: '保存が完了しましたが一部エラーが発生しました。\\nlog.txtを確認してください。'

  ##### 使いまわし
  file_exists_warning: '既にファイルが存在します。上書きしますか？'
  save_finished: '保存が完了しました。'
"""
        en = """en:
  ##### on boot
  # sub files/directory missing
  config_load_err: 'Some files or folders are not found.\\nEnter the initial settings.'

  # config file missing
  config_missing_err: 'ConfigFile not found.\\nEnter the initial settings.'

  ##### option window
  # no_tar
  opt_no_tar_lbl: "Don't use .tar files"

  # no_Alpha
  opt_no_alpha_lbl: "Don't load alphachannel images"

  # Parquet Only
  opt_parquet_only_lbl: 'Use Base Parquet only'

  # PureDanbooru root
  opt_puredanbooru_root: 'Pure-Danbooru root'

  # .tarIndex_parquet
  opt_tarindex_parquet_lbl: 'tarIndex Parquet Directory'

  # Replace Underscore
  opt_replace_underscore_lbl: 'Replace Underscore to Space'

  # Hide Metatags
  opt_hide_metatags_lbl: 'Hide Metatags'

  # Escape Curvy Brancket
  opt_escape_curvy_brancket_lbl: 'Escape Curvy Brancket'

  # Base Parquet check
  opt_base_parquet_exists_err: 'Base Parquet not found.\\nSelect Parquet directory.'

  # PureDanbooru sub directories check
  opt_puredanbooru_exists_err: 'Sub Directories not found.\\nSelect PureDanbooru directory.'

  # tarIndex parquet check
  opt_tarindex_exists_err: 'tarIndex Parquet not found.\\nSelect tarIndex Parquet directory.'

  # Save (Base parquet check)
  opt_need_base_parquet_err: 'This program need base parquet files.\\nSelect Base Parquet directory.'

  # Cancel (Value change detected)
  opt_cancel_caution: 'You have unsaved changes.\\nDo you want to save them before closing?'

  ##### search exec
  # search exec error - Hit 0 caution
  search_0_err: 'No data found for the input tags.'

  ##### result_window
  # Save from result_window - use .tar check warning
  result_use_tar_warning: 'You selected a use .tar files mode.\nImage save may be expected to take many time.\\nContinue anyway?'

  # Save from result_window - finished with error
  save_finished_with_err: 'Save Finished.\\nBut some errors occurred.\\nCheck console or log.txt'

  ##### anywhere
  file_exists_warning: 'File already exists. Overwrite?'
  save_finished: 'Save Finished.'
"""
        with open(os.path.join(os.path.dirname(__file__), 'lang', 'lang.ja.yml' ), 'w', encoding='utf-8') as f:
            f.write(ja)
        with open(os.path.join(os.path.dirname(__file__), 'lang', 'lang.en.yml' ), 'w', encoding='utf-8') as f:
            f.write(en)
        i18n.set('locale', 'en')
    
    ########## オプション画面 ##########
    # オプション画面表示
    def option_button_clicked(self, title, isInit):
        global icons
        global config, now_lang
        global purebooru, parquet_dir, idx_dir
        global img_dan, img_gel, img_alp, img_dup_dan, img_dup_gel
        global no_tar, parquet_only, noAlpha
        global replace_underscore, hide_megatags, escape_brancket

        if hasattr(self, 'option_window'):
            # すでにテーブルが表示されている場合、現在値を一応更新
            self.op_lang_sel.setCurrentText(now_lang)

            self.op_bParq.setText(parquet_dir)

            self.no_tar_chk.setChecked(no_tar)
            self.base_par_only_chk.setChecked(parquet_only)
            self.no_alpha_chk.setChecked(noAlpha)
            self.op_pure_path.setText(purebooru)
            self.op_tarIdx_path.setText(idx_dir)

            self.op_img_dan.setText(img_dan)
            self.op_img_gel.setText(img_gel)
            self.op_img_alp.setText(img_alp)
            self.op_img_dup_dan.setText(img_dup_dan)
            self.op_img_dup_gel.setText(img_dup_gel)

            self.op_tss_replace_underscore.setChecked(replace_underscore)
            self.op_tss_hide_megatags.setChecked(hide_megatags)
            self.op_tss_escape_brancket.setChecked(escape_brancket)

            self.option_window.setWindowTitle(title)
            self.option_window.show()
            self.option_window.activateWindow()
            return True # 通常起動時はTrueを返す

        self.option_window = QDialog()
        self.option_window.setWindowTitle(title)
        self.option_window.setGeometry(config.getint('OPTION', 'x', fallback=400),
                                       config.getint('OPTION', 'y', fallback=100),
                                       config.getint('OPTION', 'width', fallback=800),
                                       config.getint('OPTION', 'height', fallback=500))
        self.option_window.setWindowModality(Qt.ApplicationModal)  # モーダル設定を追加
        #self.option_window.setWindowIcon(icons[4])
        #self.option_window.setMinimumSize(800, 500)

        # Option
        option_frame = QWidget()
        option_layout = QVBoxLayout()
        option_layout.setContentsMargins(15, 15, 15, 15)
        option_frame.setLayout(option_layout)

        # language
        op_lang_frm = QWidget()
        op_lang_lay = QHBoxLayout()
        op_lang_lay.setSpacing(0)
        op_lang_lay.setContentsMargins(0, 0, 5, 0)
        op_lang_frm.setLayout(op_lang_lay)
        op_lang_lbl = QLabel('Language', alignment=Qt.AlignVCenter | Qt.AlignLeft)
        op_lang_lbl.setFixedWidth(155)
        op_lang_lbl.setStyleSheet('font-weight: bold;')
        op_lang_lay.addWidget(op_lang_lbl)
        self.op_lang_sel = QComboBox()
        self.op_lang_sel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.op_lang_sel.addItems(self.get_langlist())
        self.op_lang_sel.setCurrentText(config.get('DEFAULT', 'lang', fallback='en'))
        self.op_lang_sel.currentIndexChanged.connect(lambda: self.op_lang_sel_changed(lang=self.op_lang_sel.currentText()))
        op_lang_lay.addWidget(self.op_lang_sel)
        
        # Base Parquet
        op_path_lbl = QLabel('Base Parquet', alignment=Qt.AlignVCenter | Qt.AlignLeft)
        #op_path_lbl.setFixedWidth(90)
        op_path_lbl.setStyleSheet('font-weight: bold;')
        
        # Base Parquet
        op_bParq_frm = QWidget()
        op_bParq_lay = QHBoxLayout()
        op_bParq_lay.setSpacing(0)
        op_bParq_lay.setContentsMargins(5, 0, 5, 0)
        op_bParq_frm.setLayout(op_bParq_lay)
        op_bParq_lbl = QLabel('Path ', alignment=Qt.AlignVCenter | Qt.AlignRight)
        op_bParq_lbl.setFixedWidth(150)
        self.op_bParq = CustomLineEdit(parquet_dir)
        op_bParq_btn = QPushButton('...')
        op_bParq_btn.setFixedSize(20, 20)
        op_bParq_btn.clicked.connect(lambda: self.op_bParq_btn_clicked())
        op_bParq_lay.addWidget(op_bParq_lbl)
        op_bParq_lay.addWidget(self.op_bParq)
        op_bParq_lay.addWidget(op_bParq_btn)
        
        # PureDanbooru
        op_pure_lbl = QLabel('Pure-Danbooru', alignment=Qt.AlignVCenter | Qt.AlignLeft)
        op_pure_lbl.setStyleSheet('font-weight: bold;')
        
        # PureDanbooru
        # no_tar
        self.op_pur1_frm = QWidget()
        self.op_pur1_frm.setEnabled(not parquet_only)
        op_pur1_lay = QHBoxLayout()
        op_pur1_lay.setSpacing(0)
        op_pur1_lay.setContentsMargins(5, 0, 5, 0)
        self.op_pur1_frm.setLayout(op_pur1_lay)
        self.no_tar_chk = QCheckBox(self.escape_i18n_newline(key='lang.opt_no_tar_lbl'))
        self.no_tar_chk.setChecked(no_tar)
        self.no_tar_chk.stateChanged.connect(lambda: self.no_tar_chk_checked_changed())
        op_pur1_lay.addSpacing(65)
        op_pur1_lay.addWidget(self.no_tar_chk)
        
        # noAlpha
        self.op_pur2_frm = QWidget()
        self.op_pur2_frm.setEnabled(not parquet_only)
        op_pur2_lay = QHBoxLayout()
        op_pur2_lay.setSpacing(0)
        op_pur2_lay.setContentsMargins(5, 0, 5, 0)
        self.op_pur2_frm.setLayout(op_pur2_lay)
        self.no_alpha_chk = QCheckBox(self.escape_i18n_newline(key='lang.opt_no_alpha_lbl'))
        self.no_alpha_chk.setChecked(noAlpha)
        self.no_alpha_chk.stateChanged.connect(lambda: self.no_alpha_chk_checked_changed())
        op_pur2_lay.addSpacing(65)
        op_pur2_lay.addWidget(self.no_alpha_chk)

        # Parquet Only
        self.op_pur3_frm = QWidget()
        self.op_pur3_frm.setEnabled((no_tar or parquet_only) and not noAlpha)
        op_pur3_lay = QHBoxLayout()
        op_pur3_lay.setSpacing(0)
        op_pur3_lay.setContentsMargins(5, 0, 5, 0)
        self.op_pur3_frm.setLayout(op_pur3_lay)
        self.base_par_only_chk = QCheckBox(self.escape_i18n_newline(key='lang.opt_parquet_only_lbl'))
        self.base_par_only_chk.setChecked(parquet_only)
        self.base_par_only_chk.stateChanged.connect(lambda: self.base_par_only_chk_checked_changed())
        op_pur3_lay.addSpacing(65)
        op_pur3_lay.addWidget(self.base_par_only_chk)
        
        # PureDanbooru Path
        self.op_pur4_frm = QWidget()
        self.op_pur4_frm.setEnabled(not no_tar and not parquet_only)
        op_pur4_lay = QHBoxLayout()
        op_pur4_lay.setSpacing(0)
        op_pur4_lay.setContentsMargins(5, 0, 5, 0)
        self.op_pur4_frm.setLayout(op_pur4_lay)
        self.op_pur4_lbl = QLabel(self.escape_i18n_newline(key='lang.opt_puredanbooru_root'), alignment=Qt.AlignVCenter | Qt.AlignRight)
        self.op_pur4_lbl.setFixedWidth(150)
        self.op_pure_path = CustomLineEdit(purebooru)
        op_pure_btn = QPushButton('...')
        op_pure_btn.setFixedSize(20, 20)
        op_pure_btn.clicked.connect(lambda: self.op_pure_btn_clicked())
        op_pur4_lay.addWidget(self.op_pur4_lbl)
        op_pur4_lay.addWidget(self.op_pure_path)
        op_pur4_lay.addWidget(op_pure_btn)
        
        # TarIndex Parquet Path
        self.op_pur5_frm = QWidget()
        self.op_pur5_frm.setEnabled(not no_tar and not parquet_only)
        op_pur5_lay = QHBoxLayout()
        op_pur5_lay.setSpacing(0)
        op_pur5_lay.setContentsMargins(5, 0, 5, 0)
        self.op_pur5_frm.setLayout(op_pur5_lay)
        self.op_pur5_lbl = QLabel(self.escape_i18n_newline(key='lang.opt_tarindex_parquet_lbl'), alignment=Qt.AlignVCenter | Qt.AlignRight)
        self.op_pur5_lbl.setFixedWidth(150)
        self.op_tarIdx_path = CustomLineEdit(idx_dir)
        op_tarIdx_btn = QPushButton('...')
        op_tarIdx_btn.setFixedSize(20, 20)
        op_tarIdx_btn.clicked.connect(lambda: self.op_tarIdx_btn_clicked())
        op_pur5_lay.addWidget(self.op_pur5_lbl)
        op_pur5_lay.addWidget(self.op_tarIdx_path)
        op_pur5_lay.addWidget(op_tarIdx_btn)
        
        # Image Dir
        op_img_lbl = QLabel('Image Dir', alignment=Qt.AlignVCenter | Qt.AlignLeft)
        op_img_lbl.setStyleSheet('font-weight: bold;')

        # Danbooru
        self.op_img_frm1 = QWidget()
        self.op_img_frm1.setEnabled(no_tar and not parquet_only)
        op_img_lay1 = QHBoxLayout()
        op_img_lay1.setSpacing(0)
        op_img_lay1.setContentsMargins(5, 0, 5, 0)
        self.op_img_frm1.setLayout(op_img_lay1)
        op_img_lbl1 = QLabel('Danbooru ', alignment=Qt.AlignVCenter | Qt.AlignRight)
        op_img_lbl1.setFixedWidth(150)
        self.op_img_dan = CustomLineEdit(img_dan)
        op_img_btn1 = QPushButton('...')
        op_img_btn1.setFixedSize(20, 20)
        op_img_btn1.clicked.connect(lambda: self.opt_dirsearch_click(sendto=self.op_img_dan, title='Select Danbooru image Directory', basedir=''))
        op_img_lay1.addWidget(op_img_lbl1)
        op_img_lay1.addWidget(self.op_img_dan)
        op_img_lay1.addWidget(op_img_btn1)

        # Gelbooru
        self.op_img_frm2 = QWidget()
        self.op_img_frm2.setEnabled(no_tar and not parquet_only)
        op_img_lay2 = QHBoxLayout()
        op_img_lay2.setSpacing(0)
        op_img_lay2.setContentsMargins(5, 0, 5, 0)
        self.op_img_frm2.setLayout(op_img_lay2)
        op_img_lbl2 = QLabel('Gelbooru ', alignment=Qt.AlignVCenter | Qt.AlignRight)
        op_img_lbl2.setFixedWidth(150)
        self.op_img_gel = CustomLineEdit(img_gel)
        op_img_btn2 = QPushButton('...')
        op_img_btn2.setFixedSize(20, 20)
        op_img_btn2.clicked.connect(lambda: self.opt_dirsearch_click(sendto=self.op_img_gel, title='Select Gelbooru image Directory', basedir=''))
        op_img_lay2.addWidget(op_img_lbl2)
        op_img_lay2.addWidget(self.op_img_gel)
        op_img_lay2.addWidget(op_img_btn2)

        # Alphachannel
        self.op_img_frm3 = QWidget()
        self.op_img_frm3.setEnabled(no_tar and not parquet_only and not noAlpha)
        op_img_lay3 = QHBoxLayout()
        op_img_lay3.setSpacing(0)
        op_img_lay3.setContentsMargins(5, 0, 5, 0)
        self.op_img_frm3.setLayout(op_img_lay3)
        op_img_lbl3 = QLabel('alphachannel ', alignment=Qt.AlignVCenter | Qt.AlignRight)
        op_img_lbl3.setFixedWidth(150)
        self.op_img_alp = CustomLineEdit(img_alp)
        op_img_btn3 = QPushButton('...')
        op_img_btn3.setFixedSize(20, 20)
        op_img_btn3.clicked.connect(lambda: self.opt_dirsearch_click(sendto=self.op_img_alp, title='Select Alphachannel image Directory', basedir=''))
        op_img_lay3.addWidget(op_img_lbl3)
        op_img_lay3.addWidget(self.op_img_alp)
        op_img_lay3.addWidget(op_img_btn3)

        # Duplicate image Danbooru
        self.op_img_frm4 = QWidget()
        self.op_img_frm4.setEnabled(no_tar and not parquet_only)
        op_img_lay4 = QHBoxLayout()
        op_img_lay4.setSpacing(0)
        op_img_lay4.setContentsMargins(5, 0, 5, 0)
        self.op_img_frm4.setLayout(op_img_lay4)
        op_img_lbl4 = QLabel(' Duplicate Dan ', alignment=Qt.AlignVCenter | Qt.AlignRight)
        op_img_lbl4.setFixedWidth(150)
        self.op_img_dup_dan = CustomLineEdit(img_dup_dan)
        op_img_btn4 = QPushButton('...')
        op_img_btn4.setFixedSize(20, 20)
        op_img_btn4.clicked.connect(lambda: self.opt_dirsearch_click(sendto=self.op_img_dup_dan, title='Select Duplicate image (Danbooru) Directory', basedir=''))
        op_img_lay4.addWidget(op_img_lbl4)
        op_img_lay4.addWidget(self.op_img_dup_dan)
        op_img_lay4.addWidget(op_img_btn4)

        # Duplicate image Gelbooru
        self.op_img_frm5 = QWidget()
        self.op_img_frm5.setEnabled(no_tar and not parquet_only)
        op_img_lay5 = QHBoxLayout()
        op_img_lay5.setSpacing(0)
        op_img_lay5.setContentsMargins(5, 0, 5, 0)
        self.op_img_frm5.setLayout(op_img_lay5)
        op_img_lbl5 = QLabel(' Duplicate Gel ', alignment=Qt.AlignVCenter | Qt.AlignRight)
        op_img_lbl5.setFixedWidth(150)
        self.op_img_dup_gel = CustomLineEdit(img_dup_gel)
        op_img_btn5 = QPushButton('...')
        op_img_btn5.setFixedSize(20, 20)
        op_img_btn5.clicked.connect(lambda: self.opt_dirsearch_click(sendto=self.op_img_dup_gel, title='Select Duplicate image (Gelbooru) Directory', basedir=''))
        op_img_lay5.addWidget(op_img_lbl5)
        op_img_lay5.addWidget(self.op_img_dup_gel)
        op_img_lay5.addWidget(op_img_btn5)

        # Other
        op_other_lbl = QLabel('Other', alignment=Qt.AlignVCenter | Qt.AlignLeft)
        op_other_lbl.setStyleSheet('font-weight: bold;')
        
        # Save Tags
        op_ot1_frm = QWidget()
        op_ot1_lay = QHBoxLayout()
        op_ot1_lay.setSpacing(0)
        op_ot1_lay.setContentsMargins(5, 0, 5, 0)
        op_ot1_frm.setLayout(op_ot1_lay)
        op_ot1_lbl = QLabel('Save Tags ', alignment=Qt.AlignVCenter | Qt.AlignRight)
        op_ot1_lbl.setFixedWidth(100)
        op_ot1_lay.addWidget(op_ot1_lbl)
        op_ot1_lay.addStretch()
        
        # Replace Underscore
        op_ot2_frm = QWidget()
        op_ot2_lay = QHBoxLayout()
        op_ot2_lay.setSpacing(0)
        op_ot2_lay.setContentsMargins(5, 0, 5, 0)
        op_ot2_frm.setLayout(op_ot2_lay)
        self.op_tss_replace_underscore = QCheckBox(self.escape_i18n_newline(key='lang.opt_replace_underscore_lbl'))
        self.op_tss_replace_underscore.setChecked(replace_underscore)
        op_ot2_lay.addSpacing(65)
        op_ot2_lay.addWidget(self.op_tss_replace_underscore)
        
        # Hide Metatags
        op_ot3_frm = QWidget()
        op_ot3_lay = QHBoxLayout()
        op_ot3_lay.setSpacing(0)
        op_ot3_lay.setContentsMargins(5, 0, 5, 0)
        op_ot3_frm.setLayout(op_ot3_lay)
        self.op_tss_hide_megatags = QCheckBox(self.escape_i18n_newline(key='lang.opt_hide_metatags_lbl'))
        self.op_tss_hide_megatags.setChecked(hide_megatags)
        op_ot3_lay.addSpacing(65)
        op_ot3_lay.addWidget(self.op_tss_hide_megatags)

        # Escape Brancket
        op_ot4_frm = QWidget()
        op_ot4_lay = QHBoxLayout()
        op_ot4_lay.setSpacing(0)
        op_ot4_lay.setContentsMargins(5, 0, 5, 0)
        op_ot4_frm.setLayout(op_ot4_lay)
        self.op_tss_escape_brancket = QCheckBox(self.escape_i18n_newline(key='lang.opt_escape_curvy_brancket_lbl'))
        self.op_tss_escape_brancket.setChecked(escape_brancket)
        op_ot4_lay.addSpacing(65)
        op_ot4_lay.addWidget(self.op_tss_escape_brancket)
        
        # 保存/キャンセルボタン
        op_btn_frm = QWidget()
        op_btn_lay = QHBoxLayout()
        op_btn_lay.setSpacing(0)
        op_btn_lay.setContentsMargins(5, 0, 5, 0)
        op_btn_frm.setLayout(op_btn_lay)
        op_btn_save = QPushButton('Save')
        op_btn_cancel = QPushButton('Cancel')
        op_btn_save.clicked.connect(self.option_save_button_clicked)
        op_btn_cancel.clicked.connect(lambda: self.option_cancel_button_clicked(isInit=isInit))
        op_btn_save.setFixedSize(80, 22)
        op_btn_cancel.setFixedSize(80, 22)
        op_btn_lay.addStretch()
        op_btn_lay.addWidget(op_btn_save)
        op_btn_lay.addWidget(op_btn_cancel)
        op_btn_lay.addStretch()
        
        option_layout.addWidget(op_lang_frm)
        option_layout.addWidget(op_path_lbl)
        option_layout.addWidget(op_bParq_frm)
        option_layout.addSpacing(10)
        option_layout.addWidget(op_pure_lbl)
        option_layout.addWidget(self.op_pur1_frm)
        option_layout.addWidget(self.op_pur2_frm)
        option_layout.addWidget(self.op_pur3_frm)
        option_layout.addWidget(self.op_pur4_frm)
        option_layout.addWidget(self.op_pur5_frm)
        
        option_layout.addSpacing(10)
        option_layout.addWidget(op_img_lbl)
        option_layout.addWidget(self.op_img_frm1)
        option_layout.addWidget(self.op_img_frm2)
        option_layout.addWidget(self.op_img_frm3)
        option_layout.addWidget(self.op_img_frm4)
        option_layout.addWidget(self.op_img_frm5)
        option_layout.addSpacing(10)
        option_layout.addWidget(op_other_lbl)
        option_layout.addWidget(op_ot1_frm)
        option_layout.addWidget(op_ot2_frm)
        option_layout.addWidget(op_ot3_frm)
        option_layout.addWidget(op_ot4_frm)
        
        option_layout.addStretch()

        option_layout.addWidget(op_btn_frm)

        self.option_saved = False
        self.option_window.setLayout(option_layout)
        self.option_window.show()

        if isInit:
            # 終了待ちをする
            self.option_window.exec_()
            if hasattr(self, 'option_saved') and self.option_saved:
                return True
            else:
                return False
        else:
            return True

    # 言語ファイルの切り替え対応
    def op_lang_sel_changed(self, lang):
        global now_lang
        i18n.set('locale', lang)
        now_lang = lang

        if hasattr(self, 'option_window'):
            # 言語で変化するラベルを再セット
            self.no_tar_chk.setText(self.escape_i18n_newline(key='lang.opt_no_tar_lbl'))
            self.no_alpha_chk.setText(self.escape_i18n_newline(key='lang.opt_no_alpha_lbl'))
            self.base_par_only_chk.setText(self.escape_i18n_newline(key='lang.opt_parquet_only_lbl'))

            self.op_pur4_lbl.setText(self.escape_i18n_newline(key='lang.opt_puredanbooru_root'))
            self.op_pur5_lbl.setText(self.escape_i18n_newline(key='lang.opt_tarindex_parquet_lbl'))

            self.op_tss_replace_underscore.setText(self.escape_i18n_newline(key='lang.opt_replace_underscore_lbl'))
            self.op_tss_hide_megatags.setText(self.escape_i18n_newline(key='lang.opt_hide_metatags_lbl'))
            self.op_tss_escape_brancket.setText(self.escape_i18n_newline(key='lang.opt_escape_curvy_brancket_lbl'))
        
        if hasattr(self, 'post_order_input'):
            for l in self.lang_action:
                self.lang_action[l].setChecked(False)
            self.lang_action[lang].setChecked(True)

    # オプション画面、ベースParquetフォルダ選択ボタン
    def op_bParq_btn_clicked(self):
        # フォルダ選択
        tmppath = QFileDialog.getExistingDirectory(self, 'Select Base Parquet Directory', self.op_bParq.text().strip())
        if not tmppath:
            return

        bln = True
        while bln:
            # parquet存在チェック
            chk = self.chkBaseParquet(tmppath=tmppath)
            if not chk:
                #res = QMessageBox.warning(self, "Parquet Warning", "Parquet not found.\nSelect Base Parquet directory.", QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel)
                res = QMessageBox.warning(self, "Parquet Warning", self.escape_i18n_newline(key='lang.opt_base_parquet_exists_err'), QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel)
                if res == QMessageBox.StandardButton.Cancel:
                    return
                # 再選択
                tmppath = QFileDialog.getExistingDirectory(self, 'Select Base Parquet Directory', os.path.dirname(__file__))
                if not tmppath or tmppath == '':
                    return
            else:
                bln = False
        
        self.op_bParq.setText(tmppath)
    
    # オプション画面、PureDanbooruフォルダ選択ボタン
    def op_pure_btn_clicked(self):
        # フォルダ選択
        tmppath = QFileDialog.getExistingDirectory(self, 'Select PureDanbooru Directory', self.op_pure_path.text().strip())
        if not tmppath:
            return
        
        bln = True
        while bln:
            # PureDanbooruチェック
            chk = self.chkPureDanbooru(tmppath=tmppath)
            if not chk:
                #res = QMessageBox.warning(self, "PureDanbooru Warning", "Sub Directories not found.\nSelect PureDanbooru directory.", QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel)
                res = QMessageBox.warning(self, "PureDanbooru Warning", self.escape_i18n_newline(key='lang.opt_puredanbooru_exists_err'), QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel)
                if res == QMessageBox.StandardButton.Cancel:
                    return
                # 再選択
                tmppath = QFileDialog.getExistingDirectory(self, 'Select PureDanbooru Directory', os.path.dirname(__file__))
                if not tmppath or tmppath == '':
                    return
            else:
                bln = False
                
        self.op_pure_path.setText(tmppath)
    
    # オプション画面、no_tarチェックボタン
    def no_tar_chk_checked_changed(self):
        if self.no_tar_chk.isChecked():
            self.op_pur3_frm.setEnabled(not self.no_alpha_chk.isChecked())   # 3行目(Parquet Only)
            self.op_pur4_frm.setEnabled(False)  # 4行目(root dir)
            self.op_pur5_frm.setEnabled(False)  # 5行目(Index Parquet)
            self.op_img_frm1.setEnabled(True)   # Image Dir(Dan)
            self.op_img_frm2.setEnabled(True)   # Image Dir(Gel)
            self.op_img_frm3.setEnabled(not self.no_alpha_chk.isChecked())   # Image Dir(Alp)
            self.op_img_frm4.setEnabled(True)   # Image Dir(Dup_Dan)
            self.op_img_frm5.setEnabled(True)   # Image Dir(Dup_Gel)
        else:
            self.op_pur3_frm.setEnabled(False)
            self.op_pur4_frm.setEnabled(True)
            self.op_pur5_frm.setEnabled(True)
            self.op_img_frm1.setEnabled(False)
            self.op_img_frm2.setEnabled(False)
            self.op_img_frm3.setEnabled(False)
            self.op_img_frm4.setEnabled(False)
            self.op_img_frm5.setEnabled(False)
 
    # オプション画面、no_alphaチェックボタン
    def no_alpha_chk_checked_changed(self):
        if self.no_alpha_chk.isChecked():
            self.op_pur3_frm.setEnabled(False)
            self.op_img_frm3.setEnabled(False)
        else:
            self.op_pur3_frm.setEnabled(self.no_tar_chk.isChecked())
            self.op_img_frm3.setEnabled(self.no_tar_chk.isChecked())
    
    # オプション画面、Parquet Onlyチェックボタン
    def base_par_only_chk_checked_changed(self):
        if self.base_par_only_chk.isChecked():
            self.op_pur1_frm.setEnabled(False)
            self.op_pur2_frm.setEnabled(False)
            self.op_img_frm1.setEnabled(False)
            self.op_img_frm2.setEnabled(False)
            self.op_img_frm3.setEnabled(False)
            self.op_img_frm4.setEnabled(False)
            self.op_img_frm5.setEnabled(False)
        else:
            self.op_pur1_frm.setEnabled(True)
            self.op_pur2_frm.setEnabled(True)
            self.op_img_frm1.setEnabled(True)
            self.op_img_frm2.setEnabled(True)
            self.op_img_frm3.setEnabled(True)
            self.op_img_frm4.setEnabled(True)
            self.op_img_frm5.setEnabled(True)

    # オプション画面、TarIndex Parquetフォルダ選択ボタン
    def op_tarIdx_btn_clicked(self):
        # フォルダ選択
        tmppath = QFileDialog.getExistingDirectory(self, 'Select tarIndex Parquet Directory', self.op_tarIdx_path.text().strip())
        if not tmppath:
            return
        
        bln = True
        while bln:
            # TarIndex Parquetチェック
            chk = self.chkTarIndexParquet(tmppath=tmppath)
            if not chk:
                #res = QMessageBox.warning(self, "tarIndex Parquet Warning", "Parquet not found.\nSelect tarIndex Parquet directory.", QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
                res = QMessageBox.warning(self, "tarIndex Parquet Warning", self.escape_i18n_newline(key='lang.opt_tarindex_exists_err'), QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
                if res == QMessageBox.StandardButton.Cancel:
                    return
                # 再選択
                tmppath = QFileDialog.getExistingDirectory(self, 'Select tarIndex Parquet Directory', os.path.dirname(__file__))
                if not tmppath:
                    return
            else:
                bln = False
                
        self.op_tarIdx_path.setText(tmppath)

    # オプション画面、フォルダ選択ボタン
    def opt_dirsearch_click(self, sendto, title, basedir):
        # ファイル確認
        tmppath = QFileDialog.getExistingDirectory(self, title, basedir)
        if tmppath:
            sendto.setText(tmppath)
        
    # オプション画面、保存ボタン
    def option_save_button_clicked(self):
        global config, purebooru
        global parquet_dir, dan_post, dan_rels, dan_tags, gel_post, gel_rels, gel_tags
        global idx_dir, idx_alpha, idx_dupli, idx_image #, idx_meta
        global img_dan, img_gel, img_alp, img_dup_dan, img_dup_gel
        global no_tar, parquet_only, noAlpha, replace_underscore, hide_megatags, escape_brancket
        global pol_dan_post, pol_dan_rels, pol_dan_tags
        global pol_gel_post, pol_gel_rels, pol_gel_tags

        # ベースParquetチェック
        if not self.chkBaseParquet(tmppath=self.op_bParq.text().strip()):
            #QMessageBox.warning(self, "Parquet Warning", "Parquet not found.\nSelect Base Parquet directory.", QMessageBox.StandardButton.Ok)
            QMessageBox.warning(self, "Parquet Warning", self.escape_i18n_newline(key='lang.opt_need_base_parquet_err'), QMessageBox.StandardButton.Ok)
            return
        
        # 複合チェック
        if not self.base_par_only_chk.isChecked(): # ベースParquetのみの使用ではない
            if not self.no_tar_chk.isChecked(): # tarを使う
                if not self.chkPureDanbooru(self.op_pure_path.text().strip()): # PureDanbooruチェック
                    #QMessageBox.warning(self, "PureDanbooru Warning", "Sub Directories not found.\nSelect PureDanbooru directory.", QMessageBox.StandardButton.Ok)
                    QMessageBox.warning(self, "PureDanbooru Warning", self.escape_i18n_newline(key='lang.opt_puredanbooru_exists_err'), QMessageBox.StandardButton.Ok)
                    return
                if not self.chkTarIndexParquet(self.op_tarIdx_path.text().strip()): # TarIndexParquetチェック
                    #QMessageBox.warning(self, "tarIndex Parquet Warning", "Parquet not found.\nSelect tarIndex Parquet directory.", QMessageBox.StandardButton.Ok)
                    QMessageBox.warning(self, "tarIndex Parquet Warning", self.escape_i18n_newline(key='lang.opt_tarindex_exists_err'), QMessageBox.StandardButton.Ok)
                    return
        
        # ここまで来れるならグローバル変数の設定
        # Parquet
        if parquet_dir != self.op_bParq.text().strip():
            parquet_dir = self.op_bParq.text().strip()
            dan_post = os.path.join(parquet_dir, 'dan_post.parquet')
            dan_rels = os.path.join(parquet_dir, 'dan_rels.parquet')
            dan_tags = os.path.join(parquet_dir, 'dan_tags.parquet')
            gel_post = os.path.join(parquet_dir, 'gel_post.parquet')
            gel_rels = os.path.join(parquet_dir, 'gel_rels.parquet')
            gel_tags = os.path.join(parquet_dir, 'gel_tags.parquet')
            # 参照先を変える場合、polを再読み込み
            pol_dan_post = pl.read_parquet(dan_post)
            pol_gel_post = pl.read_parquet(gel_post)
            pol_dan_rels = pl.read_parquet(dan_rels)
            pol_gel_rels = pl.read_parquet(gel_rels)
            pol_dan_tags = pl.read_parquet(dan_tags)
            pol_gel_tags = pl.read_parquet(gel_tags)
        
        # 動作フラグ
        no_tar = self.no_tar_chk.isChecked()
        parquet_only = self.base_par_only_chk.isChecked()
        noAlpha = self.no_alpha_chk.isChecked()
        
        # PureDanbooru
        purebooru = self.op_pure_path.text().strip()

        # Tar Index
        idx_dir = self.op_tarIdx_path.text().strip()
        idx_alpha = os.path.join(idx_dir, 'tarIndex_alphachannel.parquet')
        idx_dupli = os.path.join(idx_dir, 'tarIndex_duplicate.parquet')
        idx_image = os.path.join(idx_dir, 'tarIndex_image.parquet')
        #idx_meta = os.path.join(idx_dir, 'tarIndex_metadata.parquet')
        #idx_tag = os.path.join(idx_dir, 'tarIndex_tag.parquet')

        # img_dir
        img_dan = self.op_img_dan.text().strip()
        img_gel = self.op_img_gel.text().strip()
        img_alp = self.op_img_alp.text().strip()
        img_dup_dan = self.op_img_dup_dan.text().strip()
        img_dup_gel = self.op_img_dup_gel.text().strip()
        
        # Tags_Save - Replace underscore
        replace_underscore = self.op_tss_replace_underscore.isChecked()
        # Hide Metadags
        hide_megatags = self.op_tss_hide_megatags.isChecked()
        # Escape brancket
        escape_brancket = self.op_tss_escape_brancket.isChecked()
        
        # 設定ファイルの保存
        self.saveINI()
        self.option_saved = True
        self.option_window.close()
        
        # 詳細/プレビュー画面が表示されている場合、Saveボタンを制御する
        if hasattr(self, 'result_window'):
            if parquet_only:
                self.save_alpha_result.setEnabled(False)
                self.save_imgs_result.setEnabled(False)
                self.save_both_result.setEnabled(False)
            else:
                if noAlpha:
                    self.save_alpha_result.setEnabled(False)
                else:
                    self.save_alpha_result.setEnabled(True)
                self.save_imgs_result.setEnabled(True)
                self.save_both_result.setEnabled(True)
        if hasattr(self, 'preview_window'):
            if parquet_only:
                self.save_alpha_preview.setEnabled(False)
                self.save_img_preview.setEnabled(False)
                self.save_both_preview.setEnabled(False)
            else:
                if noAlpha:
                    self.save_alpha_preview.setEnabled(False)
                else:
                    if self.alp_cnt > 0:
                        self.save_alpha_preview.setEnabled(True)
                self.preview_tab_clicked_sub(post_id=self.activate_id)
    
    # オプション画面、キャンセルボタン
    def option_cancel_button_clicked(self, isInit):
        global purebooru, parquet_dir, idx_dir
        global img_dan, img_gel, img_alp, img_dup_dan, img_dup_gel
        global no_tar, parquet_only, noAlpha, replace_underscore, hide_megatags, escape_brancket
        
        if isInit:
            self.option_window.close()
            return

        # 入力変更チェック
        chk = False
        chk = chk or parquet_dir != self.op_bParq.text().strip()
        
        chk = chk or no_tar != self.no_tar_chk.isChecked()
        chk = chk or noAlpha != self.no_alpha_chk.isChecked()
        chk = chk or parquet_only != self.base_par_only_chk.isChecked()

        chk = chk or purebooru != self.op_pure_path.text().strip()
        chk = chk or idx_dir != self.op_tarIdx_path.text().strip()

        chk = chk or img_dan != self.op_img_dan.text().strip()
        chk = chk or img_gel != self.op_img_gel.text().strip()
        chk = chk or img_alp != self.op_img_alp.text().strip()
        chk = chk or img_dup_dan != self.op_img_dup_dan.text().strip()
        chk = chk or img_dup_gel != self.op_img_dup_gel.text().strip()

        chk = chk or replace_underscore != self.op_tss_replace_underscore.isChecked()
        chk = chk or hide_megatags != self.op_tss_hide_megatags.isChecked()
        chk = chk or escape_brancket != self.op_tss_escape_brancket.isChecked()

        if chk:
            #reply = QMessageBox.warning(self, "Unsaved Changes", "You have unsaved changes.\nDo you want to save them before closing?", QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            reply = QMessageBox.warning(self, "Unsaved Changes", self.escape_i18n_newline(key='lang.opt_cancel_caution'), QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)

            if reply == QMessageBox.Save:
                self.option_save_button_clicked()
            elif reply == QMessageBox.Cancel:
                return # キャンセルなら処理を中断
            #else:
            #    Discardは何もせずそのまま画面を閉じる
            
        self.option_window.close()

    ########## メインウィンドウ関連 ##########
    # メインウィンドウ用keyReleaseイベント
    def keyReleaseEvent(self, event):
        """キーリリースイベントを処理する"""
        # アプリケーション全体の修飾キー状態を取得
        ctrl = QApplication.keyboardModifiers() & Qt.ControlModifier

        # 押されたキーを確認
        key = event.key()

        if (key == Qt.Key_Return or key == Qt.Key_Enter) and ctrl:
            # Ctrl+Enterが押された場合、検索を実行
            self.search_data()
        else:
            super().keyPressEvent(event)

    # メインウィンドウ用closeイベント
    def closeEvent(self, event):
        """ウィンドウが閉じられる際のイベントを処理する"""
        global tar_cache
        # 各種設定の保存
        self.saveINI()

        # result_window
        if hasattr(self, 'result_window') and self.result_window.isVisible():
            self.result_window.close()
            
        # tag_window
        if hasattr(self, 'tag_window') and self.tag_window.isVisible():
            self.tag_window.close()

        # option
        if hasattr(self, 'option_window') and self.option_window.isVisible():
            self.option_window.close()
            
        #for preview_window in CustomTableWidget().preview_windows.values():
        if hasattr(self, 'preview_window') and self.preview_window.isVisible():
            self.preview_window.close()

        # 勝手に解放されると思うけど念のため
        for tar_obj in tar_cache.values():
            tar_obj.close()

    # メインメニュー - 言語選択変更
    def menu_lang_changed(self, lang):
        # チェックon/offとかの制御をここでやろうかと思ってたけど別にlang_selでやっても問題なかった
        self.op_lang_sel_changed(lang=lang)

    # データソースの変更処理
    def on_sql_source_changed(self):
        global img_dan, img_gel, result_cache

        # 入力タグの再計算
        for i in range(len(self.search_entries)):
            if result_cache.get(i):
                del result_cache[i]

        for i in range(len(self.search_entries)):
            self.update_count_for_entry(index=i)
        
    # 検索ボックスの追加処理
    def add_search_box(self, isInit=False):
        # 未入力チェック
        for i in range(len(self.search_entries) - 1, -1, -1):
            dellabel, entry, label = self.search_entries[i]
            if entry.text().strip() == '':
                # 未入力エリアで入力しろ
                entry.setFocus()
                #return

        # QLineEditとQLabelの追加と管理
        entry = CustomLineEdit()
        del_label = ClickableLabel()
        del_label.setText('x')
        del_label.setAlignment((Qt.AlignVCenter | Qt.AlignLeft))
        del_label.setFixedWidth(10)
        del_label.clicked.connect(lambda: self.delLabel_clicked())
        del_label.index = len(self.search_entries)
        count_label = QLabel('Hit: -', alignment=(Qt.AlignVCenter | Qt.AlignRight))
        #count_label = QLabel(' 件数: 1,000,000', alignment=(Qt.AlignVCenter | Qt.AlignRight))
        count_label.setFixedWidth(80)
        entry.last_value = ''
        entry.index = len(self.search_entries)
        
        # QHBoxLayoutへ追加
        entry_layout = QHBoxLayout()
        entry_layout.addWidget(del_label)
        entry_layout.addWidget(entry)
        entry_layout.addWidget(count_label)
        
        # 検索frameにentry_layoutを追加
        self.search_layout.addLayout(entry_layout)
        self.search_entries.append((del_label, entry, count_label))
        
        # シグナルの追加
        entry.editingFinished.connect(lambda: self.search_entries_editingFinished(entry.index))
        
        # タブオーダーの整理
        if not isInit:
            index = 0
            for dellabel, box, label in self.search_entries:
                if index == 0:
                    QWidget.setTabOrder(self.sql_combobox, box)
                else:
                    predel, prebox, prelabel = self.search_entries[index - 1]
                    QWidget.setTabOrder(prebox, box)
                index += 1

            lasdellabel, lastbox, lastlabel = self.search_entries[index - 1]
            #QWidget.setTabOrder(lastbox, self.)
            #QWidget.setTabOrder(lastbox, self.del_button)
            QWidget.setTabOrder(lastbox, self.exec_button)

        entry.setFocus()
        return entry
    
    # 検索ボックスの削除処理
    def remove_search_box(self, index=0, from_delButton=False):
        global result_cache

        if len(self.search_entries) > 1:  # 最低1つは残す
            if from_delButton:
                # 削除ボタンからの削除は一番後ろを消す
                dellabel, entry, count_label = self.search_entries.pop()
            else:
                # タグ入力が空だった場合
                # 一番後ろだったら消さない
                if (index + 1) == len(self.search_entries):
                    return
                dellabel, entry, count_label = self.search_entries.pop(index)
                if result_cache.get(index):
                    del result_cache[index]
            
            #entryとcount_labelの削除
            self.search_layout.removeItem(entry.parent().layout())
            dellabel.deleteLater()
            entry.deleteLater()
            count_label.deleteLater()
            
        # インデックスを再調整
        for i, (d, e, cl) in enumerate(self.search_entries):
            d.index = i
            e.index = i
    
    # 削除ボタン(任意行)の実行
    def delLabel_clicked(self):
        index = self.sender().index

        # 選択行の削除処理
        self.remove_search_box(index=index)

        # 各ボックスの再計算
        for i in range(0, len(self.search_entries)):
            self.update_count_for_entry(index=i)

    # タグクリアボタン
    def clear_tags(self):
        # 下から空白にして削除
        for i in range(len(self.search_entries) - 1, -1, -1):
            dellabel, entry, label = self.search_entries[i]
            entry.setText('')
            self.remove_search_box(index=entry.index, from_delButton=False)

    # ID直指定プレビューボタン
    def post_order_button_clicked(self):
        post_id = self.post_order_input.text().strip()
        if post_id == '' or post_id is None:
            return
        
        if self.sql_combobox.currentText() == 'Danbooru':
            dp = pol_dan_post
        else:
            dp = pol_gel_post
        df = dp.filter(pl.col('id') == int(post_id)).select('id').collect()
        
        if df.height == 0:
            return
        
        self.show_preview(post_id=post_id)

    # 検索ボックスでの入力変更終了(フォーカスアウトとエンターキー両方で反応する)
    def search_entries_editingFinished(self, index):
        global result_cache
        
        d , entry, label = self.search_entries[index]
        tag = entry.text().strip().lower()
        entry.setText(tag)

        # 未入力チェック
        if tag == '':
            self.remove_search_box(index=index)

            # 各ボックスの再計算
            for i in range(index, len(self.search_entries)):
                if result_cache.get(i):
                    del result_cache[i]
                self.update_count_for_entry(index=i)
            return

        # 変更チェック
        if entry.last_value == tag:
            return

        # タグの存在チェック
        if self.sql_combobox.currentText() == 'Danbooru':
            df = pol_dan_tags
        else:
            df = pol_gel_tags
        
        # マイナス検索対応
        # ※ここでタグ取得はするけど加工したりしなかったりなので、取得を上に持って行って他の部分で使いまわしたりはしない
        chkTag = tag
        if chkTag.startswith('-'):
            chkTag = chkTag[1:]
        
        # レーティング対応
        # metadataのjsonからparquet作るとratingがタグ一覧に入ってこないから別途制御する必要がある
        # *** 要検討項目
        rating = ['rating:g', 'rating:s', 'rating:q', 'rating:e', 'rating:general', 'rating:sensitive', 'rating:questionable', 'rating:explicit']
        if chkTag not in rating:
            data = df.filter(pl.col('tag_name') == chkTag).select('tag_id').collect()

            # タグがないなら終了
            if data.height == 0:
                self.search_entries[index][2].setText('Missing Tag')
                entry.last_value = tag
                return
        
        # 入力済みタグの確保
        inputTag = {}
        for i in range(0, len(self.search_entries)):
            dellabel, entry, label = self.search_entries[i]
            inputTag[i] = {'index': i, 'tag': entry.text().strip()}

        # タグの重複チェック
        chkTag = tag
        chkBln = False    
        for i in range(0, index):
            dellabel, entry, label = self.search_entries[i]
            if chkTag != '' and entry.text().strip() == chkTag:
                label.setText('Duplicate Tag')
                entry.last_value = ''
                chkBln = True
                break

        # 重複チェックでアウトならここで終了
        if chkBln:
            entry.last_value = chkTag
            return
        
        # 未入力エリアを削除
        # for entry, label in self.search_entries:で処理すると段飛ばしが発生するので下からやる
        for i in range(len(self.search_entries) - 1, -1, -1):
            dellabel, entry, label = self.search_entries[i]
            if entry.text().strip() == '':
                self.remove_search_box(index=entry.index, from_delButton=False)

        # インデックスが変わっているタグがあればそこから再計算させるようにする
        reCalcIndex = 999
        for i in range(0, len(self.search_entries)):
            dellabel, entry, label = self.search_entries[i]
            if entry.text().strip() != inputTag[i]['tag'] or entry.text().strip() == chkTag:
                reCalcIndex = entry.index
                break

        # 再計算のためにインデックスの変更箇所からのキャッシュをクリア
        for i in range(reCalcIndex, len(self.search_entries)):
            if result_cache.get(i):
                del result_cache[i]
        
        # タグの再計算
        for i in range(reCalcIndex, len(self.search_entries)):
            self.update_count_for_entry(index=i)
        
        entry.last_value = tag
    
    # タグ入力後の自動検索
    def update_count_for_entry(self, index):
        global result_cache
        # フォーカス(インデックス)確認
        if index >= len(self.search_entries) or index < 0:
            return
        
        # 検索ボックスと現在値の取得
        dellabel, entry, count_label = self.search_entries[index]
        if entry.text().strip() == '':
            return

        # 入力タグ群の取得
        tags = tuple([e.text().strip() for d, e, l in self.search_entries[:index+1] if e.text().strip()])
        if not tags:
            # 全て空なら終了
            return
        try:
            if self.sql_combobox.currentText() == 'Danbooru':
                dp = pol_dan_post
                dt = pol_dan_tags
                dr = pol_dan_rels
            else:
                dp = pol_gel_post
                dt = pol_gel_tags
                dr = pol_gel_rels

            isNeg = False
            for tag in tags:
                if tag.startswith('-'):
                    t = tag[1:]
                    isNeg = True
                else:
                    t = tag
                    isNeg = False

                # result_cacheを確認し、タグとインデックスの位置が一致するならDataFrameを計算済みのものに再セットしつつスキップしていく
                idx = tags.index(tag)
                if result_cache.get(idx):
                    if result_cache[idx]['tag'] == tag:
                        dr = result_cache[idx]['dr']
                        continue

                rating = ['rating:g', 'rating:s', 'rating:q', 'rating:e', 'rating:general', 'rating:sensitive', 'rating:questionable', 'rating:explicit']
                if t in rating:
                    rate = 0
                    if t == 'rating:g' or t == 'rating:general':
                        rate = 0
                    elif t == 'rating:s' or t == 'rating:sensitive':
                        rate = 1
                    elif t == 'rating:q' or t == 'rating:questionable':
                        rate = 2
                    elif t == 'rating:e' or t == 'rating:explicit':
                        rate = 3
                    
                    if not isNeg:
                        dr = dr.join(
                            dp.filter(pl.col('rating') == rate).select('id'),
                            left_on='post_id',
                            right_on='id',
                            how='inner'
                        )
                    else:
                        dr = dr.join(
                            dp.filter(pl.col('rating') == rate).select('id'),
                            left_on='post_id',
                            right_on='id',
                            how='anti'
                        )
                else:
                    tag_id = dt.filter(pl.col('tag_name') == t).collect()['tag_id'][0]
                    if not isNeg:
                        dr = dr.join(
                                dr.filter(pl.col('tag_id') == tag_id).select('post_id').unique(),
                                on='post_id',
                                how='inner'
                            )
                    else:
                        dr = dr.join(
                                dr.filter(pl.col('tag_id') == tag_id).select('post_id').unique(),
                                on='post_id',
                                how='anti'
                            )
                
                if isinstance(dr, pl.LazyFrame):
                    dr = dr.collect()
                result_cache[index] = {'tag': tag, 'dr': dr.lazy()}
                
            count = dr.group_by('post_id').len().height
            count_label.setText(f"Hit: {count:,}")

            self.last_count = count # 最終的な検索結果の数を保持(検索実行ボタンの処理で使用する)
            
            # 最終行での入力終了ならボックスを追加する
            if (entry.index + 1) == len(self.search_entries):
                self.add_search_box()
            
        except Exception as e:
            print(f'Exception: {e}')
            count_label.setText('Hit: Error')
            entry.last_value = ''
            entry.count = 0

    # 検索ボタンによる本検索
    def search_data(self):
        global result_cache

        # 現状の最終検索結果が0件だったら検索しない
        if self.last_count == 0:
            #QMessageBox.warning(self, 'Error', "Input Tags cannot found data.")
            QMessageBox.warning(self, 'Error', self.escape_i18n_newline(key='lang.search_0_err'))
            return
        
        # 検索処理（複数タグでAND検索）
        tags = [entry.text().strip() for d, entry, l in self.search_entries if entry.text().strip()]
        cache_key = (self.sql_combobox.currentText(), tuple(sorted(tags)))
        if hasattr(self, 'result_window'):
            # すでにresult_window(検索結果)が表示されていて、情報が一致する場合は以降の処理を省略
            if self.result_window.cache_tag == cache_key and self.result_limit == self.limit_entry.text().strip():
                self.result_window.show()
                self.result_window.activateWindow()
                return
            elif result_cache.get(cache_key) is not None and result_cache[cache_key].get('result') is not None:
                # 前に使ったことのある検索セットならキャッシュを利用
                # if use_cache: # あたりを付けるべき？
                self.show_results(dataframe=result_cache[cache_key]['result'].collect(), cache_key=cache_key)

        if not tags:
            # 自動検索で弾くからまず来れないけど念のため
            return
        try:
            if self.sql_combobox.currentText() == "Danbooru":
                dp = pol_dan_post
            else:
                dp = pol_gel_post

            # 自動検索を経由せずここには来られない(はず)のでresult_cacheを利用する
            dr = result_cache[len(tags) - 1]['dr']
            result_posts = dp.join(
                    dr.select('post_id').unique(),
                    left_on='id',
                    right_on='post_id',
                    how='inner'
                ).sort('id').collect()
            
            # 結果の出力
            if result_posts.height > 0:
                self.show_results(dataframe=result_posts, cache_key=cache_key)
                result_cache[cache_key] = {'result': result_posts.lazy()}
        except Exception as e:
            QMessageBox.warning(self, 'Error', f"Error in 'search_data': {e}")

    ########## Result_Window関連 ##########
    # 検索結果をウィンドウで表示
    def show_results(self, dataframe, cache_key):
        global icons
        global parquet_only, noAlpha

        if hasattr(self, 'result_window'):
            # すでにresult_window(検索結果)が表示されている場合、テーブルの内容とタグの入力を照合
            # 件数増減へのチェックも追加
            if not self.result_window.cache_tag == cache_key or not self.result_limit == self.limit_entry.text().strip():
                # 不一致なら情報更新
                self.show_results_table_update(dataframe)
                self.result_source = self.sql_combobox.currentText().strip()
            
            self.result_window.cache_tag = cache_key
            self.result_window.show()
            self.result_window.activateWindow()
            return
        
        self.result_window = QWidget()
        self.result_window.setGeometry(config.getint('RESULT', 'x', fallback=400),
                                       config.getint('RESULT', 'y', fallback=100),
                                       config.getint('RESULT', 'width', fallback=800),
                                       config.getint('RESULT', 'height', fallback=500))
        # self.result_window.setWindowIcon(icons[1])
        
        layout = QVBoxLayout()
        
        # 画面照合用キャッシュの保存
        self.result_window.cache_tag = cache_key

        # カスタムテーブルウィジェットを使用
        self.detail_table = CustomTableWidget(self)
        self.detail_table.verticalHeader().hide()

        # 列ソートの実装
        self.detail_table.setSortingEnabled(True)  # これを有効にすることでソートが動作
        self.detail_table.horizontalHeader().setSortIndicatorShown(True)  # ソートインジケータを表示
        
        # 右クリックメニュー
        self.detail_table.setContextMenuPolicy(Qt.CustomContextMenu)
        def on_context_menu(pos):
            menu = QMenu()
            copy_action = menu.addAction('Copy')
            detail_action = menu.addAction('Preview')
            action = menu.exec_(self.detail_table.viewport().mapToGlobal(pos))
            if action == copy_action:
                self.detail_table.copy_selected_cells()
            elif action == detail_action:
                self.detail_table.show_preview_window()
        self.detail_table.customContextMenuRequested.connect(on_context_menu)
        
        # CSVエクスポートボタン
        button_layout = QHBoxLayout()
        export_button = QPushButton('Export CSV')
        export_button.clicked.connect(lambda: self.export_to_csv())
        export_button.setFixedSize(80, 22)
        
        # 画像表示ボタン
        preview_button = QPushButton('Preview')
        preview_button.clicked.connect(lambda: self.detail_table.show_preview_window())
        preview_button.setFixedSize(80, 22)
        
        # Auto Previewチェックボックス
        self.auto_preview = QCheckBox('Auto Preview')#####
        self.auto_preview.setChecked(config.getboolean('RESULT', 'auto_preview', fallback=False))
        
        # Save Alphaチェックボックス
        self.save_alpha_result = QCheckBox('Save alpha')#####
        self.save_alpha_result.setChecked(False)
        self.save_alpha_result.setEnabled(not noAlpha and not parquet_only)
        
        # Save Withセレクトボックス
        save_with_label = QLabel('Save With')
        self.save_with_result = QComboBox()
        self.save_with_result.addItem('Post ID')
        self.save_with_result.addItem('Filename')
        self.save_with_result.setCurrentText(config.get('RESULT', 'save_with', fallback='Post ID'))
        self.save_with_result.setEditable(False)
        self.save_with_result.setFixedSize(70, 22)
        
        # Save IMGボタン
        self.save_imgs_result = QPushButton('Save IMG')
        self.save_imgs_result.clicked.connect(lambda: self.save_data_results(mode='img'))
        self.save_imgs_result.setFixedSize(80, 22)

        # Save Tagsボタン
        save_tags_result = QPushButton('Save Tags')
        save_tags_result.clicked.connect(lambda: self.save_data_results(mode='tags'))
        save_tags_result.setFixedSize(80, 22)

        # Save Bothボタン
        self.save_both_result = QPushButton('Save Both')
        self.save_both_result.clicked.connect(lambda: self.save_data_results(mode='both'))
        self.save_both_result.setFixedSize(80, 22)

        # ボタンの動作制御
        if parquet_only:
            self.save_imgs_result.setEnabled(False)
            self.save_both_result.setEnabled(False)
        else:
            self.save_imgs_result.setEnabled(True)
            self.save_both_result.setEnabled(True)

        button_layout.addWidget(export_button, alignment=(Qt.AlignTop | Qt.AlignLeft))
        button_layout.addWidget(preview_button, alignment=(Qt.AlignTop | Qt.AlignLeft))
        button_layout.addWidget(self.auto_preview, alignment=(Qt.AlignVCenter | Qt.AlignLeft))
        button_layout.addWidget(self.save_alpha_result, alignment=(Qt.AlignVCenter | Qt.AlignLeft))
        
        button_layout.addStretch()

        button_layout.addWidget(save_with_label, alignment=(Qt.AlignVCenter | Qt.AlignRight))
        button_layout.addWidget(self.save_with_result, alignment=(Qt.AlignTop | Qt.AlignLeft))
        button_layout.addWidget(self.save_imgs_result, alignment=(Qt.AlignTop | Qt.AlignLeft))
        button_layout.addWidget(save_tags_result, alignment=(Qt.AlignTop | Qt.AlignLeft))
        button_layout.addWidget(self.save_both_result, alignment=(Qt.AlignTop | Qt.AlignLeft))
        
        layout.addLayout(button_layout)
        layout.addWidget(self.detail_table)
        
        self.result_window.setLayout(layout)

        # 詳細表示 -> データソース変更 -> Save で壊しにかかられないように
        # 詳細ウィンドウを表示した時点で使用したデータソースを保持
        self.result_source = self.sql_combobox.currentText().strip()
        self.result_limit = self.limit_entry.text().strip()

        self.show_results_table_update(dataframe=dataframe)

        if dataframe.height > 0:
            self.result_window.show()

    # 検索結果のテーブル更新
    def show_results_table_update(self, dataframe):
        limit = min(int(self.limit_entry.text()), dataframe.height)
        
        title = ''
        prev_dataframe_len = len(dataframe)
        if len(dataframe) > int(self.limit_entry.text()):
            title = f'Search Result: Find {len(dataframe)} Datas. Limit to {self.limit_entry.text()} Datas. Processing...'
        else:
            title = f'Search Result: Find {len(dataframe)} Datas. Processing...'
        self.result_window.setWindowTitle(title)
        
        self.detail_table.clear()
        if dataframe is None or dataframe.height == 0:
            self.detail_table.setRowCount(1)
            self.detail_table.setColumnCount(1)
            self.detail_table.setHorizontalHeaderLabels(['Information'])
            self.detail_table.setItem(0, 0, QTableWidgetItem('Data not find.'))
        else:
            self.detail_table.setRowCount(0)
            self.detail_table.setColumnCount(0)
            
            self.detail_table.setRowCount(limit)
            self.detail_table.setColumnCount(len(dataframe.columns))
            self.detail_table.setHorizontalHeaderLabels(list(dataframe.columns))

            # 余計な処理を避けるために件数制限
            dataframe = dataframe.head(limit)
            
            # Polars DataFrameをPythonのリスト（辞書形式）に変換
            rows = dataframe.rows(named=True)  # 列名付きのタプルのリストとして取得

            # 各セルにデータを挿入
            for i, row in enumerate(rows):
                for j, (col_name, val) in enumerate(row.items()):
                    if isinstance(val, (int, float)):  # 数値データ
                        item = NumericTableWidgetItem(val)
                        item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                    else:  # 文字列データ
                        if val is None or val == pl.Null:  # PolarsのNullを考慮
                            item = QTableWidgetItem('')
                        else:
                            item = QTableWidgetItem(str(val))
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # 編集不可
                    self.detail_table.setItem(i, j, item)
            self.last_result = dataframe
        
        if prev_dataframe_len > int(self.limit_entry.text()):
            title = f'Search Result: Find {prev_dataframe_len} Datas. Limit to {self.limit_entry.text()} Datas.'
        else:
            title = f'Search Result: Find {len(dataframe)} Datas.'
        self.result_window.setWindowTitle(title)
    
    # result_windowからのデータ保存(IMG, Tags, Both)
    def save_data_results(self, mode):
        global dan_post, dan_tags, dan_rels, gel_post, gel_tags, gel_rels
        global purebooru, img_dan, img_gel, idx_image, no_tar, tar_cache
        global last_save_path
        global replace_underscore, hide_megatags, escape_brancket

        tmpMsg = ''

        if mode == 'img':
            title = 'Save IMG from Results'
        elif mode == 'tags':
            title = 'Save Tags from Results'
        elif mode == 'both':
            title = 'Save Both from Results'
        
        ranges = self.detail_table.selectedRanges()
        if len(ranges) == 0:
            QMessageBox.information(self.result_window, title, 'No cells selected.', QMessageBox.Ok)
            return
        
        if not no_tar and mode != 'tags':
            # tmpMsg = 'You selected a use .tar files mode.\n'
            # tmpMsg += 'Image save may be expected to take many time.\n'
            # tmpMsg += 'Continue anyway?'
            tmpMsg = self.escape_i18n_newline(key='lang.result_use_tar_warning')
            res = QMessageBox.warning(self.result_window, title, tmpMsg, QMessageBox.Ok | QMessageBox.Cancel)
            if res == QMessageBox.Cancel:
                return
            tmpMsg = ''

        file_path = QFileDialog.getExistingDirectory(parent=self.result_window, caption=title, directory=last_save_path)
        if file_path:
            file_path = os.path.abspath(file_path)
            caution = False
            saveWith = self.save_with_result.currentText()
            index = []
            post_id = []
            last_save_path = file_path
            
            # 選択範囲のセルを精査し、保存するIDを取得
            for r in ranges:
                rows = range(r.topRow(), r.bottomRow() + 1)
                for i in range(rows.start, rows.stop):
                    index.append(i) # 選択行の取得
            for i in index:
                post_id.append(int(self.detail_table.item(i, 0).text())) # IDの取得 ***IDのintだったりstrだったりの不服ポイント

            if self.result_source == 'Danbooru':
                dp = pol_dan_post
            else:
                dp = pol_gel_post
            result_posts = dp.filter(pl.col('id').is_in(post_id)).collect()
            
            saveAlpha = self.save_alpha_result.isChecked()
            chkFlg = False
            img_dict = {}
            tag_dict = {}
            tmpMsg = None
            if mode == 'img' or mode == 'both': # 画像保存 or 両方
                prev = ''
                for row in result_posts.rows(named=True):
                    img_from = img_to = ''
                    alp_from = alp_to = ''
                    img_dir = alp_dir = ''
                    img_offset = alp_offset = None
                    filename = ''

                    if row['missing'] == 1:
                        caution = True
                        img_dict[row['id']] = {'from': row['id'], 'to': '', 'offset': '', 'fn': ''}
                        continue

                    # 保存ファイル名の選択
                    if saveWith == 'Post ID':
                        filename = f"{row['id']}.webp"
                        if saveAlpha and row['hasAlpha'] == 1:
                            alp_to = f"{row['id']}_alpha.webp"
                    else:
                        filename = row['file_name']
                        if saveAlpha and row['hasAlpha'] == 1:
                            alp_to = os.path.splitext(filename)[0] + '_alpha.webp'
                    img_to = os.path.abspath(os.path.join(file_path, filename))
                    alp_to = os.path.abspath(os.path.join(file_path, alp_to))
                    
                    if no_tar:
                        # 全部同じ場所に展開してるかもしれないけど
                        # img_dan/gelで別フォルダを指定できるようにしてあるので制御
                        if self.result_source == "Danbooru":
                            if row['isDup'] == 0:
                                img_dir = img_dan
                            else:
                                img_dir = img_dup_dan
                            if saveAlpha and row['hasAlpha'] == 1:
                                alp_dir = img_alp
                        else:
                            if row['isDup'] == 0:
                                img_dir = img_gel
                            else:
                                img_dir = img_dup_gel
                        img_from = os.path.abspath(os.path.join(img_dir, row['file_name']))
                        if alp_dir != '':
                            alp_from = os.path.abspath(os.path.join(alp_dir, row['file_name']))
                    else:
                        # tar使用時
                        # 画像の参照先をisDup判断
                        if row['isDup'] == 0:
                            idx = idx_image
                        else:
                            idx = idx_dupli
                        
                        df = pl.scan_parquet(idx).filter(pl.col('file_name') == row['file_name']).collect()

                        if df.height > 0:
                            tar_path = df['tar_path'][0]
                            img_offset = df['file_offset'][0]
                            img_from = os.path.abspath(os.path.join(purebooru, tar_path))
                        
                        if saveAlpha and row['hasAlpha'] == 1:
                            df = pl.scan_parquet(idx_alpha).filter(pl.col('file_name') == row['file_name']).collect()
                            if df.height > 0:
                                tar_path = df['tar_path'][0]
                                alp_offset = df['file_offset'][0]
                                alp_from = os.path.abspath(os.path.join(purebooru, tar_path))

                    img_dict[row['id']] = {'from': img_from, 'to': img_to, 'offset': img_offset, 'fn': row['file_name'], 'alp_from': alp_from, 'alp_to': alp_to, 'alp_offset': alp_offset}
                    # if prev != row['id']: ここまで
                # for _, row in result_posts.iterrows(): ここまで

                for id in img_dict:
                    # 保存先チェック(画像)
                    chkFlg = chkFlg or os.path.exists(img_dict[id]['to'])
                    if saveAlpha and img_dict[id]['alp_to'] != file_path:
                        chkFlg = chkFlg or os.path.exists(img_dict[id]['alp_to'])
                    if chkFlg:
                        break
            if mode == 'tags' or mode == 'both': # タグ保存 or 両方
                for row in result_posts.rows(named=True):
                    # 保存ファイル名の選択
                    if saveWith == 'Post ID':
                        filename = f"{row['id']}.txt"
                    else:
                        filename = row['file_name']
                        filename = os.path.splitext(filename)[0] + '.txt'
                    
                    _, savetxt = self.get_tagtext(row['id'], isSaving=True)
                    filepath = os.path.join(file_path, filename)
                    tag_dict[row['id']] = {'to': filepath, 'tag': savetxt}
                
                if not chkFlg:
                    for id in tag_dict:
                        # 保存先チェック(タグ)
                        chkFlg = chkFlg or os.path.exists(tag_dict[id]['to'])
                        if chkFlg:
                            break
        
            if mode == 'img':
                title = 'Save IMG'
            elif mode == 'tags':
                title = 'Save Tags'
            elif mode == 'both':
                title = 'Save Both'

            # 存在チェック
            if chkFlg:
                #sel = QMessageBox.warning(self.result_window, title, 'File already exists. Overwrite?', QMessageBox.YesToAll | QMessageBox.Cancel)
                sel = QMessageBox.warning(self.result_window, title, self.escape_i18n_newline(key='lang.file_exists_warning'), QMessageBox.YesToAll | QMessageBox.Cancel)
                if sel == QMessageBox.Cancel:
                    # 上書きしないなら終了
                    return
                
            # 保存処理
            # 画像は(タグに比べたら)処理が重いので後ろに回す
            if mode == 'tags' or mode == 'both':
                for id in tag_dict:
                    with open(tag_dict[id]['to'], 'w', encoding='utf-8') as f:
                        f.write(tag_dict[id]['tag'])
            if mode == 'img' or mode == 'both':
                for id in img_dict:
                    # no_tarモードはshutilで楽してたけどtar使用でバイナリ使う形になったから方向性を統一
                    bin = None
                    # ファイルの存在チェック(tar/no_tar共通)
                    if os.path.exists(img_dict[id]['from']):
                        # ファイル処理でなんかエラー吐くかもなのでtryで囲む
                        try:
                            if no_tar:
                                # no_tar
                                with open(img_dict[id]['from'], 'rb') as f:
                                    bin = f.read()
                                with open(img_dict[id]['to'], 'wb') as f:
                                    f.write(bin)
                                if saveAlpha and img_dict[id]['alp_from'] != '':
                                    with open(img_dict[id]['alp_from'], 'rb') as f:
                                        bin = f.read()
                                    with open(img_dict[id]['alp_to'], 'wb') as f:
                                        f.write(bin)
                            else:
                                # 圧縮ファイルからファイルを獲得
                                if img_dict[id]['from'] != '':
                                    bin = self.get_tardata(tar_path=img_dict[id]['from'], filename=img_dict[id]['fn'], file_offset=img_dict[id]['offset'])
                                    if bin is not None:
                                        with open(img_dict[id]['to'], 'wb') as f:
                                            f.write(bin)
                                if saveAlpha and img_dict[id]['alp_from'] != '':
                                    bin = self.get_tardata(tar_path=img_dict[id]['alp_from'], filename=img_dict[id]['fn'], file_offset=img_dict[id]['alp_offset'])
                                    if bin is not None:
                                        with open(img_dict[id]['alp_to'], 'wb') as f:
                                            f.write(bin)
                        except Exception as e:
                            caution = True
                            if tmpMsg is not None:
                                tmpMsg += f"\n'save_data_results' Failed (Exception): {e}"
                            else:
                                tmpMsg = f"'save_data_results' Failed (Exception): {e}"
                    else:
                        caution = True
                        if tmpMsg is not None:
                            tmpMsg += f"\n'save_data_results' Failed (File Not Found): {img_dict[id]['from']}"
                        else:
                            tmpMsg = f"'save_data_results' Failed (File Not Found): {img_dict[id]['from']}"

            #description = 'Save Finished.'
            description = self.escape_i18n_newline(key='lang.save_finished')
            if caution:
                description = self.escape_i18n_newline(key='lang.save_finished_with_err')
                print(tmpMsg)

                with open('.\log.txt', 'a', encoding='utf-8') as f:
                    f.write(tmpMsg)
            QMessageBox.information(self.result_window, title, description)

    # CSVエクスポート(Detail)
    def export_to_csv(self):
        global last_save_path
        file_path, _ = QFileDialog.getSaveFileName(parent=self.result_window, caption='Save CSV', directory=last_save_path, filter='CSV files (*.csv)')
        if file_path:
            if os.path.isdir(file_path[0]):
                last_save_path = file_path[0]
            else:
                last_save_path = os.path.dirname(file_path[0])
            self.last_result.write_csv(file_path)
            QMessageBox.information(self.result_window, 'Save CSV', f"Save to {file_path}")

    ########## Preview_Window関連 ##########
    # プレビューウィンドウの表示
    def show_preview(self, post_id):
        global icons
        isInit = False
        
        if hasattr(self, 'preview_window'):
            if post_id in self.prev_id:
                # 選択したポストが既存の表示群に存在するなら切り替えて表示して終わり
                self.preview_tab_clicked_sub(post_id=post_id)

                self.preview_window.show()
                #self.preview_window.activateWindow() # ちょっとうざかった
                return
        
        # 親子関係の確認のためのポスト精査
        if not hasattr(self, 'result_window'):
            # ID直指定プレビューのための動作
            self.result_source = self.sql_combobox.currentText().strip()
        if self.result_source == "Danbooru":
            dp = pol_dan_post
        else:
            # gelに親子関係ないっぽいけど一応
            dp = pol_gel_post
        
        post_id = int(post_id)
        post = dp.filter(pl.col('id') == post_id).with_columns(pl.lit(2).alias('group')).collect()
        parent = post.head(0)
        sibling = post.head(0)

        # Gelbooruは親子関係ない…までは良かったけど全部0埋めしてやがって兄弟で爆発するので回避
        if self.result_source == "Danbooru":
            if post['parent_id'][0] is not None:
                parent = dp.filter(pl.col('id') == post['parent_id'][0]).with_columns(pl.lit(1).alias('group')).collect()
                sibling = dp.filter(pl.col('parent_id') == post['parent_id'][0], pl.col('id') != post_id).with_columns(pl.lit(3).alias('group')).collect()
        child = dp.filter(pl.col('parent_id') == post_id).with_columns(pl.lit(4).alias('group')).collect()
        basedf = pl.concat([post, parent, sibling, child]).sort(pl.col('group'), pl.col('id'))
        post_id = str(post_id) # intしたりstrしたりめっちゃ不服。parquetをstrに変えるべき？***
        
        if not hasattr(self, 'preview_window'):
            # 初回表示の場合
            isInit = True
            # preview_windowのベース
            self.preview_window = QWidget()
            self.preview_window.setGeometry(config.getint('PREVIEW', 'x', fallback=1200),
                                            config.getint('PREVIEW', 'y', fallback=100),
                                            config.getint('PREVIEW', 'width', fallback=600),
                                            config.getint('PREVIEW', 'height', fallback=400))
            self.preview_window.setMinimumSize(600, 400)
            # self.preview_window.setWindowIcon(icons[2])

            self.layout = QVBoxLayout()
            self.layout.setContentsMargins(5,1,5,1)
            
            # ボタンエリア
            button_frame = QWidget()
            button_layout = QHBoxLayout()
            button_frame.setLayout(button_layout)

            # Danbooru/Gelbooruのページを開く
            web_button = QPushButton('\U0001F30F')
            web_button.clicked.connect(lambda: self.open_web_page())
            web_button.setFixedSize(50, 22)
            
            # Alphaボタン
            self.save_alpha_preview = QCheckBox('Alpha')
            self.save_alpha_preview.setChecked(False)
            self.save_alpha_preview.setFixedSize(50, 22)
            self.save_alpha_preview.clicked.connect(lambda: self.save_alpha_preview_changed())

            # Save Withセレクトボックス
            save_with_label = QLabel('Save With')
            self.save_with_preview = QComboBox()
            self.save_with_preview.addItem('Post ID')
            self.save_with_preview.addItem('Filename')
            self.save_with_preview.setCurrentText(config.get('PREVIEW', 'save_with', fallback='Post ID'))
            self.save_with_preview.setEditable(False)
            self.save_with_preview.setFixedSize(70, 22)

            # Save IMGボタン
            self.save_img_preview = QPushButton('Save IMG')
            self.save_img_preview.clicked.connect(lambda: self.save_data_preview(mode='img'))
            self.save_img_preview.setFixedSize(80, 22)
            
            # Save Tagsボタン
            self.save_tag_preview = QPushButton('Save Tags')
            self.save_tag_preview.clicked.connect(lambda: self.save_data_preview(mode='tags'))
            self.save_tag_preview.setFixedSize(80, 22)
            
            # Save Bothボタン
            self.save_both_preview = QPushButton('Save Both')
            self.save_both_preview.clicked.connect(lambda: self.save_data_preview(mode='both'))
            self.save_both_preview.setFixedSize(80, 22)

            # Save Groupボタン
            self.save_group_preview = QPushButton('Save Group')
            self.save_group_preview.clicked.connect(lambda: self.save_groupdata_preview())
            self.save_group_preview.setFixedSize(80, 22)

            # ボタンエリアへのボタン追加
            button_layout.addWidget(web_button, alignment=(Qt.AlignTop | Qt.AlignLeft))                 # web
            button_layout.addWidget(self.save_alpha_preview, alignment=(Qt.AlignVCenter | Qt.AlignLeft))    # alpha
            button_layout.addStretch()                                                                  # ストレッチ
            button_layout.addWidget(save_with_label, alignment=(Qt.AlignVCenter | Qt.AlignRight))       # save_with(ラベル)
            button_layout.addWidget(self.save_with_preview, alignment=(Qt.AlignTop | Qt.AlignLeft))        # save_with(本体)
            button_layout.addWidget(self.save_img_preview, alignment=(Qt.AlignTop | Qt.AlignLeft))      # save_img
            button_layout.addWidget(self.save_tag_preview, alignment=(Qt.AlignTop | Qt.AlignLeft))      # save_tag
            button_layout.addWidget(self.save_both_preview, alignment=(Qt.AlignTop | Qt.AlignLeft))     # save_both
            button_layout.addWidget(self.save_group_preview, alignment=(Qt.AlignTop | Qt.AlignLeft))    # save_group
        else:
            # 2回目以降の表示の場合、画面更新のためにレイアウトからタブフレームとビューフレーム(Base)を削除
            # ラベルを空にするとかじゃなんでか消えなかった
            self.layout.removeWidget(self.view_frame_base)
            self.layout.removeWidget(self.tab_frame)
            self.layout.removeWidget(self.tab_frame_alpha)
        ### if not hasattr(self, 'preview_window'):

        # タブエリア
        self.tab_frame = QScrollArea()
        self.tab_frame.setFixedHeight(130)
        self.tab_frame.setWidgetResizable(False)
        self.tab_frame.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tab_frame.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        tab_layout = QGridLayout()
        tab_layout.setHorizontalSpacing(5)
        tab_layout.setVerticalSpacing(2)

        tab_widget = QWidget() # これ追加しないとラベルが何故かマージンがうまく行かない
        tab_widget.setLayout(tab_layout)
        tab_widget.setMinimumHeight(105)
        tab_widget.setMaximumHeight(105)
        tab_widget.setMinimumWidth(5+(100*len(basedf))+5*(len(basedf)-1)+5)
        tab_widget.setMaximumWidth(5+(100*len(basedf))+5*(len(basedf)-1)+5)

        self.tab_frame.setWidget(tab_widget)
        tab_layout.setContentsMargins(5, 5, 5, 5)

        # アルファ用
        self.tab_frame_alpha = QScrollArea()
        self.tab_frame_alpha.setFixedHeight(130)
        self.tab_frame_alpha.setWidgetResizable(False)
        self.tab_frame_alpha.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tab_frame_alpha.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        tab_layout_alpha = QGridLayout()
        tab_layout_alpha.setHorizontalSpacing(5)
        tab_layout_alpha.setVerticalSpacing(2)

        tab_widget_alp = QWidget() # これ追加しないとラベルが何故かマージンがうまく行かない
        tab_widget_alp.setLayout(tab_layout_alpha)
        tab_widget_alp.setMinimumHeight(105)
        tab_widget_alp.setMaximumHeight(105)
        tab_widget_alp.setMinimumWidth(5+(100*len(basedf))+5*(len(basedf)-1)+5)
        tab_widget_alp.setMaximumWidth(5+(100*len(basedf))+5*(len(basedf)-1)+5)

        self.tab_frame_alpha.setWidget(tab_widget_alp)
        tab_layout_alpha.setContentsMargins(5, 5, 5, 5)

        if isInit:
            # 初回表示の場合、レイアウトにボタンフレームを追加
            self.layout.addWidget(button_frame)
            self.layout.addSpacing(0)

        self.layout.addWidget(self.tab_frame)
        self.layout.addWidget(self.tab_frame_alpha)
        self.layout.addSpacing(0)

        ########## ごみかすうんち ##########
        cnt = 0
        self.tab_lbl = {}
        self.img_bin = {}
        self.view_frame_base = QWidget()
        self.view_frame_base_layout = QVBoxLayout()
        self.view_frame_base.setLayout(self.view_frame_base_layout)
        self.view_frame = {}
        view_layout = {}
        self.prev_filename = {}
        self.save_tags_string = {}
        self.view_text = {}
        self.view_lbl = {}
        self.view_pix = {}
        self.alp_tab = {}
        self.alp_lbl = {}
        self.alp_bin = {}
        self.alp_cnt = 0
        self.view_lbl_alp = {}
        self.view_pix_alp = {}
        self.prev_id = []
        
        self.preview_window.setWindowTitle(f'Preview ID: {post_id} Processing...')

        for df in basedf.rows(named=True):
            id = str(df['id']) # ゴチャゴチャして見辛いので退避

            # プレビューウィンドウに表示中のID群を確保
            self.prev_id.append(id)
            
            # タブ用のラベルを作成
            self.tab_lbl[id] = ClickableLabel() # ラベルでイベント発火してselfがラベル自身になるのでself.しなくて良い
            self.tab_lbl[id].setAlignment(Qt.AlignCenter)
            self.tab_lbl[id].setFixedSize(100, 100)
            self.tab_lbl[id].setStyleSheet('border: 1px solid black;')
            self.tab_lbl[id].index = id # タブクリック用のインデックス
            self.tab_lbl[id].clicked.connect(lambda: self.preview_tab_clicked())

            # ファイル名、ファイルのバイナリ取得
            isDup = str(df['isDup'])
            missing = str(df['missing'])
            self.prev_filename[id] = df['file_name']
            self.img_bin[id] = self.getPixMap(isDup=isDup, missing=missing, filename=self.prev_filename[id])

            # 一応ケア
            if self.prev_filename[id] is None:
                self.prev_filename[id] = ''

            tmpPix = QPixmap()
            if self.img_bin[id] is not None:
                # ファイルがなかった場合やparqeut_onlyの場合、bin = Noneなのでこけないよう対処
                tmpPix.loadFromData(self.img_bin[id])
            
            self.update_image(lbl=self.tab_lbl[id], pixmap=tmpPix, isTab=True) # タブ用画像のリサイズ
            tab_layout.addWidget(self.tab_lbl[id], 0, cnt)                     # タブを追加

            # アルファ画像の取得
            # アルファ用のタブラベルを作成
            self.alp_lbl[id] = ClickableLabel()
            self.alp_lbl[id].setAlignment(Qt.AlignCenter)
            self.alp_lbl[id].setFixedSize(100, 100)
            self.alp_lbl[id].setStyleSheet('border: 1px solid black;')
            self.alp_lbl[id].index = id # タブクリック用のインデックス
            self.alp_lbl[id].clicked.connect(lambda: self.preview_tab_clicked())
            #self.update_image(lbl=self.alp_lbl[id], pixmap=QPixmap().loadFromData(self.alp_bin[id]), isTab=False)
            
            # binの取得と貼り付け
            hasAlpha = str(df['hasAlpha'])
            self.alp_bin[id] = None
            self.alp_bin[id] = self.getPixMap_Alpha(hasAlpha=hasAlpha, filename=self.prev_filename[id])
            alppix = QPixmap()
            if self.alp_bin[id] is not None:
                alppix.loadFromData(self.alp_bin[id])
                self.alp_cnt += 1
            self.update_image(lbl=self.alp_lbl[id], pixmap=alppix, isTab=True)
            tab_layout_alpha.addWidget(self.alp_lbl[id], 1, cnt)
            
            ########## タブ関連ここまで ##########

            # メインビュー用のフレームとレイアウトの作成
            self.view_frame[id] = QWidget()
            view_layout[id] = QHBoxLayout()
            view_layout[id].setContentsMargins(5,1,5,1)
            self.view_frame[id].setLayout(view_layout[id])
            self.view_frame[id].setVisible(False)
            
            # メインビュー用項目
            # テキスト
            self.view_text[id] = QTextEdit()
            self.view_text[id].setReadOnly(True)
            self.view_text[id].width = 300
            self.view_text[id].setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
            self.view_text[id].setFontPointSize(12)
            # 表示用と保存用を取得
            view_txt, save_txt = self.get_tagtext(post_id=id, isSaving=False)
            self.view_text[id].setText(view_txt)
            self.save_tags_string[id] = save_txt
            
            # 画像ラベル
            self.view_lbl[id] = QLabel()
            self.view_lbl[id].setAlignment(Qt.AlignCenter)
            self.view_lbl[id].setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.view_pix[id] = tmpPix
            if self.img_bin[id] is None:
                self.view_lbl[id].setText(f"Image Not Found.")
            
            # ビュー用アルファ
            self.view_lbl_alp[id] = QLabel()
            self.view_lbl_alp[id].setAlignment(Qt.AlignCenter)
            self.view_lbl_alp[id].setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.view_pix_alp[id] = alppix
            if self.alp_bin[id] is None:
                self.view_lbl_alp[id].setText(f"Image Not Found.")
            
            view_layout[id].addWidget(self.view_text[id])
            view_layout[id].setSpacing(10)
            view_layout[id].addWidget(self.view_lbl[id])
            view_layout[id].addWidget(self.view_lbl_alp[id])

            # preview_window用のレイアウトにメインビュー用のフレームを追加
            self.view_frame_base_layout.addWidget(self.view_frame[id])
            cnt += 1
        ### for df in basedf.rows(named=True): ここまで
        
        # 親子関係がない画像の場合、タブフレームを非表示にする
        if len(self.tab_lbl) == 1:
            self.tab_frame.setVisible(False)
            self.tab_frame_alpha.setVisible(False)
            self.save_group_preview.setEnabled(False)
        elif len(self.tab_lbl) > 1: # >1指定しておかないと初期起動の時にちらつく
            if self.save_alpha_preview.isChecked():
                if not noAlpha:
                    self.tab_frame_alpha.setVisible(True)
            else:
                self.tab_frame.setVisible(True)
            self.save_group_preview.setEnabled(True)
            
        # 現在表示中のIDを設定
        self.activate_id = post_id
        
        # 表示の有無やボタン制御の処理
        if self.alp_cnt == 0 or noAlpha: # noAlphaの時点でcnt0のはずだけど一応
            self.save_alpha_preview.setChecked(False)
            self.save_alpha_preview.setEnabled(False)
        else:
            self.save_alpha_preview.setEnabled(True)
        self.save_alpha_preview_changed()
        self.preview_tab_clicked_sub(post_id=post_id)
        
        if isInit:
            self.preview_window.setLayout(self.layout)
            # ウィンドウにイベントフィルタをインストール
            self.preview_window.installEventFilter(self)
        self.layout.addWidget(self.view_frame_base)

        self.preview_window.show()
        self.preview_window.activateWindow()
    
    # プレビューウィンドウ - タブクリック
    def preview_tab_clicked(self):
        if hasattr(self, 'preview_window'):
            self.preview_tab_clicked_sub(post_id=self.sender().index)

    # 処理を使いまわしたかったので分離
    def preview_tab_clicked_sub(self, post_id):
        global parquet_only

        if post_id == 0:
            return

        self.save_img_preview.setEnabled(False)
        self.save_both_preview.setEnabled(False)

        for id in self.prev_id:
            self.view_frame[id].setVisible(False) # 一度全ビューを非表示
            self.tab_lbl[id].setStyleSheet('border: 1px solid black;')  # タブのボーダー変更
            self.alp_lbl[id].setStyleSheet('border: 1px solid black;')
        self.view_frame[post_id].setVisible(True) # クリックしたタブのインデックスから該当のものを表示

        self.activate_id = post_id                # アクティブIDの変更

        self.tab_lbl[post_id].setStyleSheet('border: 2px solid blue;')
        self.alp_lbl[post_id].setStyleSheet('border: 2px solid blue;')

        if self.save_alpha_preview.isChecked():
            self.update_image(lbl=self.view_lbl_alp[post_id], pixmap=self.view_pix_alp[post_id], isTab=False)
        else:
            self.update_image(lbl=self.view_lbl[post_id], pixmap=self.view_pix[post_id], isTab=False)
        self.preview_window.setWindowTitle(f'Preview ID: {post_id}')

        if not parquet_only and self.img_bin[post_id] is not None:
            self.save_img_preview.setEnabled(True)
            self.save_both_preview.setEnabled(True)
    
    # アルファボタンの切り替え
    def save_alpha_preview_changed(self):
        post_id = self.activate_id
        
        # タブの差し替えとビューに表示する画像の切り替え
        if self.save_alpha_preview.isChecked():
            if len(self.tab_lbl) > 1:
                self.tab_frame.setVisible(False)
                self.tab_frame_alpha.setVisible(True)
                for id in self.prev_id:
                    self.view_lbl[id].setVisible(False)
                    self.view_lbl_alp[id].setVisible(True)
            else:
                self.view_lbl[post_id].setVisible(False)
                self.view_lbl_alp[post_id].setVisible(True)
        else:
            if len(self.tab_lbl) > 1:
                self.tab_frame.setVisible(True)
                self.tab_frame_alpha.setVisible(False)
                for id in self.prev_id:
                    self.view_lbl[id].setVisible(True)
                    self.view_lbl_alp[id].setVisible(False)
            else:
                self.view_lbl[post_id].setVisible(True)
                self.view_lbl_alp[post_id].setVisible(False)
        
        self.preview_tab_clicked_sub(post_id=post_id)

    # プレビューウィンドウ - pixmap取得
    def getPixMap(self, isDup, missing, filename):
        global img_dan, img_gel
        global img_dup_dan, img_dup_gel
        global idx_image, idx_dupli
        global purebooru, no_tar, parquet_only

        img_path = None
        bin = None

        if parquet_only or missing == '1': 
            # parquetのみの場合、あるいはmissingな時は意味がないのでここで終了
            return bin
        
        if no_tar:
            # tarを使わない場合
            
            # 詳細ウィンドウ表示時のデータソースでフォルダ分岐
            if self.result_source == "Danbooru":
                if isDup == '0':
                    img_path = os.path.join(img_dan, filename)
                else:
                    img_path = os.path.join(img_dup_dan, filename)
            else:
                if isDup == '0':
                    img_path = os.path.join(img_gel, filename)
                else:
                    img_path = os.path.join(img_dup_gel, filename)
            
            if os.path.exists(img_path):
                with open(img_path, 'rb') as r:
                    bin = r.read()
            else:
                print(f"Error in 'getPixMap'. File not found.\n  {img_path}")
        else:
            # tarを使う場合
            # Duplicateの方に格納されているか否かのチェック
            if isDup == '0':
                idx = idx_image
            else:
                idx = idx_dupli

            df = pl.scan_parquet(idx).filter(pl.col('file_name') == filename).collect()
            tar_path = df['tar_path'][0]
            file_offset = df['file_offset'][0]
            
            tar_path = os.path.abspath(os.path.join(purebooru, tar_path))
            bin = self.get_tardata(tar_path=tar_path, filename=filename, file_offset=file_offset)
            if bin is None:
                print(f"Error in 'getPixMap'.")
        return bin

    # プレビューウィンドウ - pixmap取得
    def getPixMap_Alpha(self, hasAlpha, filename):
        global purebooru, no_tar, parquet_only, noAlpha
        global img_alp, idx_alpha

        img_path = None
        bin = None

        if hasAlpha == '0' or noAlpha:
            # alpha持ってないかアルファ拒否モードなら意味がないので終了
            return bin
        
        if no_tar:
            # tarを使わない場合
            
            # 詳細ウィンドウ表示時のデータソースでフォルダ分岐
            if self.result_source == "Danbooru":
                img_path = os.path.join(img_alp, filename)
            else:
                # Gelbooruにalpha画像はないけどコピペだから多少はね
                #img_path = os.path.join(img_alp, filename)
                return bin
            
            if os.path.exists(img_path):
                with open(img_path, 'rb') as r:
                    bin = r.read()
            else:
                print(f"Error in 'getPixMap_Alpha'. File not found.\n  {img_path}")
        else:
            # tarを使う場合
            df = pl.scan_parquet(idx_alpha).filter(pl.col('file_name') == filename).collect()
            tar_path = df['tar_path'][0]
            file_offset = df['file_offset'][0]
            
            tar_path = os.path.abspath(os.path.join(purebooru, tar_path))
            bin = self.get_tardata(tar_path=tar_path, filename=filename, file_offset=file_offset)
            if bin is None:
                print(f"Error in 'getPixMap'.")
        return bin

    # プレビューウィンドウ - 表示用のタグテキスト処理とセーブ用のテキスト出力
    def get_tagtext(self, post_id, isSaving):
        global replace_underscore, hide_megatags, escape_brancket
        
        # ソース圧縮
        if self.sql_combobox.currentText() == 'Danbooru':
            dr = pol_dan_rels
            dt = pol_dan_tags
            # カスタムソートキーを定義
            sort_key_expr = (
                pl.when(pl.col("category") == 1).then(1)
                .when(pl.col("category") == 3).then(2)
                .when(pl.col("category") == 4).then(3)
                .when(pl.col("category") == 0).then(4)
                .when(pl.col("category") == 5).then(5)
                .when(pl.col("category") == 6).then(6)
                .otherwise(999)
            )
        else:
            dr = pol_gel_rels
            dt = pol_gel_tags
            sort_key_expr = (
                pl.when(pl.col("category") == 1).then(1)
                .when(pl.col("category") == 4).then(2)
                .when(pl.col("category") == 3).then(3)
                .when(pl.col("category") == 5).then(4)
                .when(pl.col("category") == 6).then(5)
                .when(pl.col("category") == 0).then(6)
                .otherwise(999)
            )
        
        # 情報を取得
        post_id = int(post_id) # ***不服ポイント
        df = dt.join(
            dr.filter(pl.col('post_id') == post_id).select('tag_id'),
            on='tag_id',
            how='inner'
        ).with_columns(sort_key_expr.alias('sort_key')).sort(
            'sort_key',
            pl.col('tag_name')
        )
        post_id = str(post_id) # ***不服ポイント

        rep_dic = {}

        if replace_underscore:
            rep_dic['_'] = ' '
        if escape_brancket:
            rep_dic['('] = '\\('
            rep_dic[')'] = '\\)'

        if len(rep_dic) > 0:
            df = df.with_columns(pl.col('tag_name').str.replace_many(rep_dic).alias('tag_name'))

        if hide_megatags:
            df = df.filter(pl.col('category') < 5)

        df = df.collect()
        view_txt = 'No DATA'
        save_txt = ''
        if df.height == 0:
            return view_txt, save_txt
        
        # タグ保存用
        save_txt = ', '.join(df['tag_name'])
        if isSaving:
            return view_txt, save_txt
        
        # タグ情報を文字列に整形してセット
        #   Dan: 1(Artist), 3(Copyright), 4(Character), 0(General), 5(Metadata), 6(Deprecated?)
        #   Gel: 1(Artist), 4(Character), 3(Copyright), 6(Deprecated), 5(Metadata), 0(General)
        # 　5と6は必要なの？ 特に6(Deprecated)の廃止されたタグ
        separate = 99
        tag_text = None
        for row in df.rows(named=True):
            # 画面出力用の調整
            if row['category'] == separate:
                tag_text += f"\n{row['tag_name']}"
            elif row['category'] == 0: # General
                if tag_text == None:
                    tag_text = f"----- General -----\n{row['tag_name']}"
                else:
                    tag_text += f"\n----- General -----\n{row['tag_name']}"
                separate = row['category']
            elif row['category'] == 1: # Artist
                if tag_text == None:
                    tag_text = f"----- Artist -----\n{row['tag_name']}"
                else:
                    tag_text += f"\n----- Artist -----\n{row['tag_name']}"
                separate = row['category']
            elif row['category'] == 3: # Copyright
                if tag_text == None:
                    tag_text = f"----- Copyright -----\n{row['tag_name']}"
                else:
                    tag_text += f"\n----- Copyright -----\n{row['tag_name']}"
                separate = row['category']
            elif row['category'] == 4: # Character
                if tag_text == None:
                    tag_text = f"----- Character -----\n{row['tag_name']}"
                else:
                    tag_text += f"\n----- Character -----\n{row['tag_name']}"
                separate = row['category']
            elif row['category'] == 5: # Meta
                if tag_text == None:
                    tag_text = f"----- Meta -----\n{row['tag_name']}"
                else:
                    tag_text += f"\n----- Meta -----\n{row['tag_name']}"
                separate = row['category']
            elif row['category'] == 6: # Deprecated
                if tag_text == None:
                    tag_text = f"----- Deprecated -----\n{row['tag_name']}"
                else:
                    tag_text += f"\n----- Deprecated -----\n{row['tag_name']}"
                separate = row['category']
        view_txt = tag_text

        return view_txt, save_txt

    # プレビューウィンドウ - イベントフィルタ
    def eventFilter(self, obj, event):
        if hasattr(self, 'preview_window'):
            if obj == self.preview_window and event.type() == QEvent.Resize:
                if self.activate_id != 0:
                    self.update_image(lbl=self.view_lbl[self.activate_id], pixmap=self.view_pix[self.activate_id], isTab=False)
        return super().eventFilter(obj, event)
    
    # 画像のリサイズ処理
    def update_image(self, lbl, pixmap, isTab):
        """画像のリサイズ処理"""
        if pixmap:
            if not pixmap.width() > 0:
                return

            # 新しいサイズを計算
            if not isTab:
                # ウィンドウの最小サイズに合わせてリサイズ
                # ※関数をウィンドウリサイズイベントにも使いまわしてるのでこっちを先に
                if len(self.prev_id) > 1:
                    new_width = self.preview_window.width() - 320
                    new_height = self.preview_window.height() - 27 - 32 - 135
                else:
                    new_width = self.preview_window.width() - 320
                    new_height = self.preview_window.height() - 27 - 32
            else:
                # タブ画像用
                new_width = lbl.width()
                new_height = lbl.height()

            # 画像のアスペクト比を計算
            aspect_ratio = pixmap.width() / pixmap.height()

            if new_width / new_height > aspect_ratio:
                new_width = int(new_height * aspect_ratio)
            else:
                new_height = int(new_width / aspect_ratio)

            # アスペクト比を維持してリサイズ
            pixmap_resized = pixmap.scaled(new_width, new_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            lbl.setPixmap(pixmap_resized)
            lbl.width = new_width
            lbl.height = new_height

    # Webページ表示ボタン
    def open_web_page(self):
        post_id = self.activate_id
        if self.sql_combobox.currentText() == 'Danbooru':
            url = f"https://danbooru.donmai.us/posts/{post_id}"
        else:
            url = f"https://gelbooru.com/index.php?page=post&s=view&id={post_id}"
        webbrowser.open(url)
    
    # データ保存ボタン(Preview)
    def save_data_preview(self, mode):
        global last_save_path

        if mode == 'img':
            title = 'Save IMG from Preview'
        elif mode == 'tags':
            title = 'Save Tags from Preview'
        elif mode == 'both':
            title = 'Save Both from Preview'
        
        if self.save_with_preview.currentText() == 'Post ID':
            fn = self.activate_id
        else:
            fn = os.path.splitext(self.prev_filename[self.activate_id])[0]

        if mode == 'both':
            file_path = QFileDialog.getExistingDirectory(parent=self.preview_window, caption=title, directory=last_save_path)
        else:
            if mode == 'img':
                if self.save_alpha_preview.isChecked():
                    fn = f"{fn}_alpha.webp"
                else:
                    fn = f"{fn}.webp"
                filter_str = 'Image files (*.webp)'
            else:
                fn = f"{fn}.txt"
                filter_str = 'Tags files (*.txt)'
            file_path = QFileDialog.getSaveFileName(parent=self.preview_window, caption=title, directory=os.path.join(last_save_path, fn), filter=filter_str)
        
        if file_path == '' or not file_path or file_path[0] == '':
            return

        if mode == 'both':
            if self.save_alpha_preview.isChecked():
                img_path = os.path.join(file_path, f"{fn}_alpha.webp")
            else:    
                img_path = os.path.join(file_path, f"{fn}.webp")
            txt_path = os.path.join(file_path, f"{fn}.txt")
            last_save_path = file_path
        else:
            img_path = file_path[0]
            txt_path = file_path[0]
            last_save_path = os.path.dirname(file_path[0])

        # 存在チェック
        # 前は画像とタグのチェックもここでやってたけど、そもそもダイアログさんがチェックしてくれてた
        chkFlg = False
        if mode == 'both':
            chkFlg = os.path.exists(img_path)
            chkFlg = chkFlg or os.path.exists(txt_path)

        if chkFlg:
            #sel = QMessageBox.warning(self.preview_window, title, 'File already exists. Overwrite?', QMessageBox.Yes | QMessageBox.No)
            sel = QMessageBox.warning(self.preview_window, title, self.escape_i18n_newline(key='lang.file_exists_warning'), QMessageBox.Yes | QMessageBox.No)
            if sel == QMessageBox.No:
                # 上書きしないなら終了
                return
        
        if mode == 'img' or mode == 'both':
            # 画像の保存
            with open(img_path, 'wb') as f:
                if self.save_alpha_preview.isChecked():
                    f.write(self.alp_bin[self.activate_id])
                else:
                    f.write(self.img_bin[self.activate_id])

        if mode == 'tags' or mode == 'both':
            # タグの保存
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(self.save_tags_string[self.activate_id])

        #QMessageBox.information(self.preview_window, title, 'Save Finished.')
        QMessageBox.information(self.preview_window, title, self.escape_i18n_newline(key='lang.save_finished'))
    
    # グループ保存ボタン(Preview)
    def save_groupdata_preview(self):
        global parquet_only, last_save_path

        title = 'Save Group from Preview'
        file_path = QFileDialog.getExistingDirectory(parent=self.preview_window, caption=title, directory=last_save_path)
        
        if file_path == '' or not file_path:
            return
        
        last_save_path = file_path
        
        # 保存先チェック
        # ファイル名のリストアップ
        datas = {}
        for id in self.prev_id:
            img_bin = None
            img_to = None
            tag_to = None

            if self.save_with_preview.currentText() == 'Post ID':
                if not parquet_only:
                    if self.save_alpha_preview.isChecked():
                        img_bin = self.alp_bin[id]
                        img_to = os.path.join(file_path, f'{id}_alpha.webp')
                    else:
                        img_bin = self.img_bin[id]
                        img_to = os.path.join(file_path, f'{id}.webp')
                tag_to = os.path.join(file_path, f'{id}.txt')
            else:
                if not parquet_only:
                    if self.save_alpha_preview.isChecked():
                        img_bin = self.alp_bin[id]
                        img_to = os.path.splitext(self.prev_filename[id])[0] + '_alpha.webp'
                        img_to = os.path.join(file_path, img_to)
                    else:
                        img_bin = self.img_bin[id]
                        img_to = self.prev_filename[id]
                        img_to = os.path.join(file_path, img_to)
                tag_to = os.path.splitext(self.prev_filename[id])[0] + '.txt'
                tag_to = os.path.join(file_path, tag_to)
            datas[id] = {'img_bin': img_bin, 'img_to': img_to, 'tag_to': tag_to}
        
        # 存在確認
        chkFlg = False
        for id in datas:
            chkFlg = chkFlg or os.path.exists(datas[id]['tag_to'])
            if datas[id]['img_to'] is not None:
                chkFlg = chkFlg or os.path.exists(datas[id]['img_to'])
            if chkFlg:
                break
        if chkFlg:
            #sel = QMessageBox.warning(self.preview_window, title, 'File already exists. Overwrite?', QMessageBox.Yes | QMessageBox.No)
            sel = QMessageBox.warning(self.preview_window, title, self.escape_i18n_newline(key='lang.file_exists_warning'), QMessageBox.Yes | QMessageBox.No)
            if sel == QMessageBox.No:
                # 上書きしないなら終了
                return
            
        # 保存処理
        for id in datas:
            if datas[id]['img_bin'] is not None:
                with open(datas[id]['img_to'], 'wb') as f:
                    f.write(datas[id]['img_bin'])
            with open(datas[id]['tag_to'], 'w') as f:
                f.write(self.save_tags_string[id])

        #QMessageBox.information(self.preview_window, title, 'Save Finished.')
        QMessageBox.information(self.preview_window, title, self.escape_i18n_newline(key='lang.save_finished'))
    
    ########## タグビューワー ##########
    # タグビューワー表示ボタンクリック (タグビューワーウィンドウを表示)
    def tag_view_button_clicked(self, isInit):
        global icons
        global config
        global tag_search_limit
        
        if hasattr(self, 'tag_window'):
            # すでにテーブルが表示されている場合、単純に表示
            if self.tag_window is not None:
                self.tag_window.show()
                #self.tag_window.raise_()
                self.tag_window.activateWindow()
            return
        
        self.tag_window = QWidget()
        self.tag_window.setWindowTitle('PureDanbooru Tag viewer')
        self.tag_window.setGeometry(config.getint('TAG_VIEW', 'x', fallback=1200),
                                    config.getint('TAG_VIEW', 'y', fallback=100),
                                    config.getint('TAG_VIEW', 'width', fallback=500),
                                    config.getint('TAG_VIEW', 'height', fallback=500))
        # self.tag_window.setWindowIcon(icons[3])
        #self.tag_window.setMinimumSize(500, 500)

        layout = QVBoxLayout()
        
        # カスタムテーブルウィジェットを使用
        self.tag_view = CustomTableWidget(self)
        self.tag_view.verticalHeader().hide()

        # 列ソートの実装
        self.tag_view.setSortingEnabled(True)  # これを有効にすることでソートが動作
        self.tag_view.horizontalHeader().setSortIndicatorShown(True)  # ソートインジケータを表示
        
        # 右クリックメニュー
        self.tag_view.setContextMenuPolicy(Qt.CustomContextMenu)
        def on_context_menu(pos):
            menu = QMenu()
            copy_action = menu.addAction('Copy')
            send_action = menu.addAction('Send')
            action = menu.exec_(self.tag_view.viewport().mapToGlobal(pos))
            if action == copy_action:
                self.tag_view.copy_selected_cells()
            elif action == send_action:
                self.tag_view.send_selected_tag()
        self.tag_view.customContextMenuRequested.connect(on_context_menu)

        # 設定ヘッダ
        tag_setting_frame = QWidget()
        tag_setting_layout = QHBoxLayout()
        tag_setting_layout.setSpacing(0)
        tag_setting_layout.setContentsMargins(5,1,5,1)
        tag_setting_frame.setLayout(tag_setting_layout)

        # タグ入力ボックス
        tag_search_lbl = QLabel('Tag: ')
        self.tag_search_entry = CustomLineEdit('')
        self.tag_search_entry.last_value = ''
        self.tag_search_entry.editingFinished.connect(lambda: self.tag_search_entry_editingFinished())
        tag_setting_layout.addWidget(tag_search_lbl)
        tag_setting_layout.addWidget(self.tag_search_entry)

        # 検索限界値の設定
        tag_search_limit_lbl = QLabel('   Limit: ')
        self.tag_search_limit = CustomLineEdit(tag_search_limit)
        self.tag_search_limit.setValidator(QIntValidator(1, 1000000, self))
        self.tag_search_limit.setFixedWidth(60)
        tag_setting_layout.addWidget(tag_search_limit_lbl)
        tag_setting_layout.addWidget(self.tag_search_limit)

        # 設定ヘッダ2行目
        tag_setting_frame2 = QWidget()
        tag_setting_layout2 = QHBoxLayout()
        tag_setting_layout2.setSpacing(0)
        tag_setting_layout2.setContentsMargins(5,1,5,1)
        tag_setting_frame2.setLayout(tag_setting_layout2)
        
        # カテゴリ選択ボックス
        tag_category_lbl = QLabel('Category: ')
        self.tag_category_select = QComboBox()
        self.tag_category_select.addItems(['a:ALL', '0:General', '1:Artist', '3:Copyright', '4:Character', '5:Metadata', '6:Deprecated'])
        self.tag_category_select.setCurrentText('a:ALL')
        self.tag_category_select.setEditable(False)
        tag_setting_layout2.addWidget(tag_category_lbl)
        tag_setting_layout2.addWidget(self.tag_category_select)

        # Order
        tag_order_lbl = QLabel('  Order: ')
        self.tag_order_select = QComboBox()
        self.tag_order_select.addItems(['tag_id', 'tag_name', 'count', 'category'])
        self.tag_order_select.setCurrentText('tag_id')
        self.tag_order_select.setEditable(False)
        tag_setting_layout2.addWidget(tag_order_lbl)
        tag_setting_layout2.addWidget(self.tag_order_select)

        # Order sub
        self.tag_order_sub = QComboBox()
        self.tag_order_sub.addItems(['ASC', 'DESC'])
        self.tag_order_sub.setCurrentText('ASC')
        self.tag_order_sub.setEditable(False)
        tag_setting_layout2.addWidget(self.tag_order_sub)
        tag_setting_layout2.addStretch()

        layout.addWidget(tag_setting_frame)
        layout.addWidget(tag_setting_frame2)
        layout.addWidget(self.tag_view)
        
        self.tag_window.setLayout(layout)

        if self.sql_combobox.currentText() == 'Danbooru':
            d_tags = pol_dan_tags
        else:
            d_tags = pol_gel_tags

        d_tags = d_tags.head(int(tag_search_limit)).collect()
        self.tag_viewer_table_update(d_tags)
        
        if not isInit:
            self.tag_window.show()

    # タグビューワーでの検索ボックスeditingFinishedイベント
    def tag_search_entry_editingFinished(self):
        """タグビューワーでの検索イベント"""
        global tag_search_limit

        val = self.tag_search_entry.text().strip().lower()
        self.tag_search_entry.setText(val)
        category = self.tag_category_select.currentText()
        order = self.tag_order_select.currentText()
        order_sub = self.tag_order_sub.currentText()
        source = self.sql_combobox.currentText()
        query = f'{val}_{category}_{order}_{order_sub}_{source}'
        # 前回の入力と同じなら何もしない
        if query == self.tag_search_entry.last_value:
            return
        
        #df = pd.DataFrame
        if self.sql_combobox.currentText() == 'Danbooru':
            df = pol_dan_tags
        else:
            df = pol_gel_tags
        
        tmpval = val.replace('*', '.*?').replace('(', '\(').replace(')', '\)')
        tmpval = '^' + tmpval + '$'
        cat0 = self.tag_category_select.currentText()[0]
        if cat0 != 'a':
            df = df.filter(pl.col('category') == int(cat0))
        datas = df.filter(pl.col('tag_name').str.contains(tmpval)).sort(order, descending=(order_sub == 'DESC')).collect()
        self.tag_viewer_table_update(datas)
        self.tag_search_entry.last_value = query

    # タグビューワーのテーブル更新処理
    def tag_viewer_table_update(self, dataframe):
        limit = min(len(dataframe), int(self.tag_search_limit.text().strip()))
        
        title = ''
        if len(dataframe) > limit:
            title = f'Tags Search: Find {len(dataframe)} Tags. Limit to {limit}. Processing...'
        else:
            title = f'Tags Search: Find {len(dataframe)} Tags. Processing...'
        self.tag_window.setWindowTitle(title)

        self.tag_view.setRowCount(0)

        # データが空だった場合の処理
        if dataframe is None or dataframe.height == 0:
            self.tag_view.setRowCount(1)
            self.tag_view.setColumnCount(1)
            self.tag_view.setHorizontalHeaderLabels(['Information'])
            self.tag_view.setItem(0, 0, QTableWidgetItem('Datas not found.'))
            return
        
        self.tag_view.setRowCount(limit)
        self.tag_view.setColumnCount(len(dataframe.columns))
        self.tag_view.setHorizontalHeaderLabels(list(dataframe.columns))
    
        # 余計な処理を避けるために件数制限
        dataframe = dataframe.head(limit)
        
        # Polars DataFrameをPythonのリスト（辞書形式）に変換
        rows = dataframe.rows(named=True)  # 列名付きのタプルのリストとして取得

        # 各セルにデータを挿入
        for i, row in enumerate(rows):
            for j, (col_name, val) in enumerate(row.items()):
                if isinstance(val, (int, float)):  # 数値データ
                    item = NumericTableWidgetItem(val)
                    item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                else:  # 文字列データ
                    if val is None or val == pl.Null:  # PolarsのNullを考慮
                        item = QTableWidgetItem('')
                    else:
                        item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # 編集不可
                self.tag_view.setItem(i, j, item)

        if len(dataframe) > limit:
            title = f'Tags Search: Find {len(dataframe)} Tags. Limit to {limit}.'
        else:
            title = f'Tags Search: Find {len(dataframe)} Tags.'
        self.tag_window.setWindowTitle(title)

    ########## 参照元があっちこっちになりそうな奴 ##########
    # tarからbinを取得する関数
    def get_tardata(self, tar_path, filename, file_offset):
        bin = None
        # 事前に処理してるはずだけど一応
        tar_path = os.path.abspath(tar_path)
        if os.path.exists(tar_path):
            # データの取得
            if tar_path not in tar_cache:
                if not os.path.exists(tar_path):
                    #return filename, img_path, ret
                    return bin
                tar_cache[tar_path] = tarfile.open(tar_path, 'r')
            member = tar_cache[tar_path].getmember(filename)
            if member.offset_data == file_offset:
                bin = tar_cache[tar_path].extractfile(member).read()

        return bin

    # 言語一覧リスト取得
    def get_langlist(self):
        langs = os.listdir(os.path.join(os.path.dirname(__file__), 'lang'))
        cnt = 0
        for l in langs:
            langs[cnt] = l.replace('lang.', '').replace('.yml', '')
            cnt += 1
        return langs

    # i18nの\nエスケープを置換
    def escape_i18n_newline(self, key):
        txt = i18n.t(key)
        txt = txt.replace('\\n', '\n')
        return txt

    # どわりんさいこー
    def get_icon(self):
        global icons
        b64 = []
        b64.append("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")
        b64.append("iVBORw0KGgoAAAANSUhEUgAAAGQAAABkCAYAAABw4pVUAAABhGlDQ1BJQ0MgcHJvZmlsZQAAKJF9kT1Iw0AYht+mSkUrDnYQdchQO9lFRRxLFYtgobQVWnUwufQPmjQkKS6OgmvBwZ/FqoOLs64OroIg+APiLjgpukiJ3yWFFjHecdzDe9/7cvcdIDSrTDV7YoCqWUY6ERdz+VUx8Ao/xjBAMyIxU09mFrPwHF/38PH9LsqzvOv+HINKwWSATySOMd2wiDeIZzctnfM+cYiVJYX4nHjSoAsSP3JddvmNc8lhgWeGjGx6njhELJa6WO5iVjZU4hnisKJqlC/kXFY4b3FWq3XWvid/YbCgrWS4TmscCSwhiRREyKijgiosRGnXSDGRpvO4h3/U8afIJZOrAkaOBdSgQnL84H/wu7dmcXrKTQrGgd4X2/6YAAK7QKth29/Htt06AfzPwJXW8deawNwn6Y2OFj4ChraBi+uOJu8BlzvAyJMuGZIj+WkJxSLwfkbflAeGb4H+Nbdv7XOcPgBZ6tXyDXBwCERKlL3u8e6+7r79W9Pu3w+hMXK5G/JDsgAAAAZiS0dEAP8A/wD/oL2nkwAAAAlwSFlzAAALEwAACxMBAJqcGAAAAAd0SU1FB+kDGwsfJ1kiHrAAACAASURBVHja7X15nF1Vle63Tt17UwlJKqmKCAKCSDAMEWR6LWogoJIg+kIgLUrjD2mlZVABGTo8MISgQVHkYUCgEemHtDRIN60YUCY7DDZhDFMgTMFOIGSuVEKq6t57vvfHPefstfbep5IYArzud/kVqbr33HP2Xmuv8Vtrb8F77EVyPwDjAHwCwAEAtn+bH7EIwFwADwKYIyKP4v+/AiZMIDmL5EsseQHYrJ8BXi9lz57w350JY0l+j+SCt5v4m8GkBdmYxv73YUTKw0nenJIk04wO6Wau9JSbK1mR180kD/8vLBHpJKac3aJfulHEal2XKqIrwhefqZ/UXpsyVV9Ji+9s1HOLe3E203TSfyVGHEw2f002C0JtHBMcAd2/TcWAJvN7pvrzgphNyxhzz40cS/79NCXT5q/TND34/2FGNLcjmz9O02aaskWosomnaTMjZvaTXe+InhO66YhqrnU/aXFN/ndq76n/zhmbDjw+99xmyrT5Y7K53Zaim2wZO9E8FuBZFNlLCEjSVnZdNudsKJL/SeR/EABEWgOl+m4+eFFv6AvU9AhCSqdK9VvrmmSg8baGNY/AJUnSduN7miFp2tgGkKkCfosAkqRSMrGGI6jHA+HGjcqxzN5HMsJKTmjvfnRczwgg3t3c92WA8WffvpzgzCSpLHnPMYTN+niInEfiEABI2ipxRhAQ8Qmb/Z8AhBBKa1XrC/VKphQCBRCg5SSZ3VMk/8NNt6A9FQ+UJPliR4FE5pI2GxAhQNwLkYskqdz3nmFImtZPEOB8EDtJWzUy+Lpb/VD0y2lEu9qp6CESLPKCB8WX4dFcSRvF3Sd/eIsHdGpQPZyUnNCWLwCSyNyY1gFiIURmSFK57l1nCJv9UwH5LgXtSVKNSU7GAIL5qiZAcWqFGQckIxQVVTNZQWZK8qBS0VAyS+Opnvz+3iJw6kw868KCyW6x2O+37EstzhSgF+CFktRmvisMYbN/MIBpBM6BhANls9/TzO6BhnxukUcHQ/VFRR97v5LPcqIKxUplRJrcAojbqELSkEtLzdMC/a0FQ/yAgulJUlv/jjGEzb4RgEwjeJpQIBWPGY1+Jw2KrFRG1K5ulBCiRTFKbNDWpPtmGXrlmyfZO1jXTdS49RjhfT+TlrZBHlP68vldRmB60jZo9RZnSNrsGwzg+wBPA6RkUM5z0jaA2lBqdVGoqfz6wDUyXrFmNLWh1gqJMIwUz4lgsARaahUizgaV+l9OqJJKOP/s0ssgPDdpa98kSUn+AvmYBuA0MLJCGn0tW0ECJESYEbf1d+tXHV8ALCw9W4yhJkF2n8LWsHX/7HcnDa17C9XfmdGW4mNmBGXLcGf3KlZO5lmw4CazIekY0d0np3ra6ItLjeA0AaZtKnWTTZOO9VMBngMSSaXdY0Zvi6DSWoGFbaCbBpBCkLqAjnQ/Rn04JuUSBqaZJLnPhTS2QjOoReu09WShUzkZwSlKBRUeliK2ODXF/H9UdiRjoAjBxvoIUwiS56SN9VO3iMpKG+tPAHAFgPakMtj/LKIAlItvrLqxpMH/YWJ3AYVZiCF2FXtWvrASnjsMz35IzGDn1wiKGCjugCibFngsElmk61vel+CUpG3wdW8bQ9LGW+MFuI6QnQJm1NeroExPRJQqstrfN8eEDQDtneB95nS877+FLoK2F/Rc5HD5qPje2TohCH/8EZZlkpdUhngOznoQXAjghKQy5L7NZkjaeGsbADeCOCSpDvE+WwfjTtEL7DCAzxt5OxYMUl3v/x1LjZRdF/1u9PviIkG4sYQRrTf27DMhIAGd3soiehybVIYs2TwbQk4FGWWGKANYqJNCjSvbIHRCAm0odS5LGU46OyDqfoXeZphplNwwK4fBJG3JkBPBWwSQmsDI2BVt0Jk7CPlbaaHO0sY6S+TKEAA8BOTUzZKQtLHuWBC/BICkupVSU2u97GzJnX3/M6p7MYC4DCBZkfRI9FpuAgW8e+igdcBxlszH0mxdfu3fJJWtbtxkhqT1ddsB/B2AvZLqUI8ZesKhPs5TJfHZeo8XnZUVZ3PISASxMZQo4YTnTAycG/A5ErlnGcMNXYgI7eYB+FxSHbp4E1UWzwAtM5z2oIZvAtUgATqbhktNqYdCLWTX1Pv7sXz5cixfvgI9PT3erMPfGY4wonl9taPGlv1LMw947jixEY9R7zMiMUMBYC8AZ2ySDUnraw8GebpvwNL62iLGAFn4+Gbg4k9IJehATw8jsBPPPPscPv3Zz2HrbXfC1tvuiI7ObXDhRTPRaNQ9Zrof8WyQ1vMmxU9P0uh5VCbpOJDtoTc3FfiaQJhI+9fGSHx6Wu85eOMlhDwVoCTVYYoZa5w3T5W+NmLKYvx+RJszl0FYQqX5iD/8/i7c/8BDZjgXTP8elr65DGBarHRLf72y03zEhVEuJFZS60podVnMLY3RIw/0gvk6J8JJm9G2kiLt77FSwlQInLpRDEnrayYBPCqmX8VfGSpN4jAKFunxYhGK9YREpTd0SgQAli5bHrdpbBYxQMtrowKaHMxVeEaUIn3jxitGmgrVm6d4VMQu4hhAb9yFZsjzZ5pRhaS59AujlppHpf09kzZCQngiQCQ1JR39a5x0andS4B6ufXdQEcaJcrHCzCqnSd5Va3E8u4Vze9JBvcJTlZvKJCRQNqmTAH0d3TyoUiPiBaoF0+jZf3HMpXlunk9ji4b5XGrDc9f9xAEZ0uzvPhzExHJL5elU0jOtToSLCXkxh4tyvZll92orwbHb2kSBUwxVoon77coupNZ4hFRxuR2fsYllyUWjKVwCU3RiNGY3LU0npv3dhw8gITy+JR0dSjq6AQ+TY0EQrUdbopszIRdjMfkmGzWLYmAeOLa1xc1aW5IozFsRLbMrbmWyEEo9XilSv5rWVJlgmABXdCZROw+GAtlzs8vEW2iOJa3nNPtWKynpyK88PsqQtG/VWAGmMBK9MhM7KkKIkhCdVsonzwzXoNbRZmV70sUUFKKtra0kYpIsl0iL8gkKtaCJJsrTEbVSWTgeViUVtkiUnFE5Kvl3FI9E+2Si6BN4XipbEXpsU9K+1WMDhhA4BgTaBo1wKqxvlTFaosRU4xEs8mvaWNLo5QKzgMNKnG13QVilREIqiY9QqdS4qCCOgQy7VExR3EDzX77orIZKVZGK8s00VkyXQglxE7cwBM4BatE0k/raiDzLfEzAEAGm0DOERhsKi8HlDxGli4W+jaGT+Gxl5aJL346IU31lKgtJkhlkWm8PqcMrtDGlN1aNacCtVpf/dd5TAZrlC0qUbSlsRRo491oaDJxAggPVDJBTDEPSvpUTCIzWKrbZt1IFVNoFjJsreulp0frTTyQCkJSFAabS47F6LgBIRJtgZzxFEZVwiKNVktqI08aHtJ5i4alpKaebhRiwgJ6X6bSHaJcZNupP+1ZaJwIc3exbNUFLyBFCImnvNBfmJHDqRfnXHsJn4FN66YrCHUyL1c3A48qMehJPr7VJzoA0E6i0gHO1JySGaGno4fiwrCCyyhkCmEyzxcPQd1IhAcWfM0x2QzSTACSDOnPaHgEAlYyLE6LBqS4YEw/AYQZfmrGLEll3o+dfWIAXFrwMshnFL3TB1rynnilRWWLGpnEKBqU9kboi0tWCqZwhVR1MXrdVLDKviI8ezwSuIsYUVSgUUfLnEpG6FYMfTAAAafat2A/AIyDR1j6qpa56l6uEp6riyFE18dLfCtduoWy5dybo7u7Gjh8ei56167A5r3WrF6O9vR3WrROLSNJHC1tv1ev9rXWaUbdWrcWRrdLMr61UETVXgyYHXMmYndWGObyoNea2QV2ZeViep8j3r4AcB6BghqGtUjtGfysMwiS081WjjHm9Xt9sZuQ2pIiaPSuqix36+nrx/IKX8MqrC7Fgwcu4/8E/YfYdd5l7femLR+HAjx+A0aM/jD12G4MPfGCbAXCNWFAL5znmtWNWdGxClY4RrujO3bdt0KiWEBDjJO1dfivAyUn7+5xB713meVv56hoAUzYr1papzX3kcTz/wotI07QUd8qHd/c9f8Sv/vlfAob09ryOarGy7V2azSaeeXY+7n/gT7jiZ/+ABS++sknMvuD8c3DU5M9jt4/sCkkSr/zBZ0VZzT0GwFni12shaPYuh4D/Is3epf8JyvZtg1sMaa5fNjCGDRsLaEw9Vn3oCkG8YoYSBPCqa36BU751dkC0vrVLUGlrM9zrr/fj4bmP4cqrfo6bf/1vmy2Fp578NZx79ul4/zZbl9i6GDAlxtbGmx0Yx70AeHRfVAG9PnDRCEKrJYAGilWVDFp3Z9e5LK963+eSxCoTmaVO2krDEKhs8txHnsAFF12MP9z1x1ICDx26FQ4e9wl0dXViRMdwvLrwz/jN7XeWXj/rymtx731zcPWVP8GBf7W/QzFhyrWsypRoXFEwinZV2uxEWNK/faUMhSsicqH1tkyWVFQeKg+ixNSR6lS8CQIlfByAlhREwV4BmOKNN97ErJ9di4svuTx63TdP+ToO+8x47PLhD2GHHbZH+6BBZm7da3qwaNHr+M3td+K8ad8Pvv/c/AX41PjP4Q+zb8Gh4w8qbGaAaRmXz9NkgjjCKIzOWXO6AhBtg9/vs9iZsczTclG4RdpE4cdBVQBV9tO4ZnnWNixbL43UATzw0MM4/m9PxasL/2zeHzt2N5x52ik4aNyB2GH77SK1P+7VMXwYOnb/CHbffQyOnvx5XHHVz/HTK64NnvXZw6dgzj2/wYEH/hVsTwIjqQxVqcySiokBKzuAtvat0Vy/FAlR7lUUuHfKDYDJec4qjafsgSCaNbpVXZskcYb87JrrcNChXzDMeN/7unDDdVdizt2/xd98eYplBrxMrk0/QUCM3mVn/PD7F+CHM+MluEcd81UsXvR6BH6g8UCLwJixVDsHKDsKaZ/od5vrl5j0cl74FWRp6dIpGoQSDyfxW5BoilTiOEGZDfnmabakaeaM/4VnnngAXz5mMoYPH1aC2YQZBClg49Z11WoF3zr1RJz1nRBRXbZsBS7+0WVoNBpFE1GRQvFyZzQmUSOGYRGIxgdaNI/Gvy5/Y31qwpZ3KvhVZU4dQph6OEDqZT4jjFWrqNI2cO3eQeM+jv+4/w6cfeY30dU1Mht2qiBlH/P2A1eV3sly6ZVKgrPPOBkf3XO3UDKvvh7/PudPhgGic4iw1ftOjTt7YngikSI+xcjE6FjJnQPbAuBKf2gLyXQmmgw8dCkqDb1KFNpGZdHZ4QEYcv7U03Hbzf+I/ffb25Qb5T0l9NBHF8gqSXblk84jItDZ2Ylp550Zfe6VV1+HRrPRkgLjOTFMQpImh2dTSSoXJqF2ENIihqRFAC0S5kppaNSYS0RSo2qMVGYYtzoNzE1fXy+efvq5KFFu+uXVOP/cMzL15NW1FKpIq83UJj+VJPuZwRyvOGT8pzB06JDg2bf95g7Me+rZrKcErdR7gM3Qy2ekFucXWj+jBNlNfCNO6t+t0WVRKED4XrXGPmJPE4Vt03cGQKxctQpnTZ2Oi2b+JCDIV7/yRUyZ/PmWfSEzJ0Ns+lupP/2MoBWN9FLyjqDDhw3FWaefEl0QDz30cFAzAB9BzRenRn4DZ0ADd4RPjcRv3cilQERcYwsVEIW8RN+pMW0zcoiUCtvOxdsSwcnNq6+8hi8d93e44qrro8RoNlPrlkh5NUsr1R0WbmvmC/3snJPqAw7YJzqGX992O5rNprKHEa1i1JF1u4u5q8qcgt7ay9LGirqMkFZlCXVCzYs085ZnDyEUyTAL+rR0NmruI49j/GFH4u577y+1HWmaKul1wJNoBgtNnYLG98UCeUp90CtJJbo6R8RjoAfnYumy5Q6P0WrKaxMpIO6iucc6RYQHXmmGMFImqR/mxMoZMWoYVaznVMCggOntI2xZZ0rit7/7PT5+0BFYtHjgnSnqjbr17qglThRSqEA11dKgVa8oSSqw//xHiBEdw0vHsaa7xwWBvmQIDWQMTyI0dp8vUtFVjtnCT4C0NOgTz7N2xQ4wYo6iKgVmwv49Wu+nqDcauObaG3DklBOCSX/x6C+EKqvRND6CqMIL0oeH6Y03vi61I6Tr7oYPHVrKkLVvrTV1AeIhkTRpeRZFEWJsjVpG9AooSCSxlIsfPeewp49Rh1W8HgFIO3ASvb19+OGPZuGUb4e9K3fP/mdMnhRu4tZoNkxDDmirOjy0xpbgMET+bdRsV3WtVi1lSG9vn1fZ4mG/tN5mvnByqMpWBfgxWNTLynVKaoNpA7q4iQrtQPzOC99N7unpwbnTLsZ3Z/womOzvb/8njD/owAAzyQlBP+AivY0JvIyd6GSt+m6uEVTVfl7wJgC6e9aUZ4+3GlI4P06NWGzfqxBSUbsr6Cu0iIQ2pCLRpL9NyhV5J7HJx7xDNm8xFlpclyqzu3Llapxx9gX45a9C8Gn2bTfg0IM/2SrfbzZDLKSv30GhcF24OlYyKRnVaGMKpkVcLYAHZeSQwepV3aUMGTJ4sKlDC3JyIhH1nRc+iCkuR5Bmas0o0SJTGbqDVzqp3Di/EUU8kctXh6QKX26NeOnS5Tjx5LOizPjtrb/AYZ8eV6iAZkRC+vr6bCWL6II71cfuLaai2kMcZCAmY5AxMs8mEFi2YkUpQ97XNSKoSKFnI10KxatKEa+SMVPplaEfNJa6EubtCcS2tkAaJAttml1XbqRF6f+ixW/g6yediT/cE7q1N91wJSYedogJ4tI0lJD169d7FYO0rQdQzfx+gR+DBPAAGVjitdcWRZkx+X9OQMeIDoRoVSTVzxI8JIAew47eBAQaa1+LZ9+DDDIjLoWVFL01xuI33sSXjjspyoyrfjoTR006PCi/jKmsdeve8ppydDLURx8iHe4MU9+hoib6+/tx7S/+KcqQz356XFBMDT+56NcrR6GNNJp7b6x9DSQiEiK5JKThsIu0dWSvIyNFLSbdfOu/4aGHHw+G9b0LzsJXj/trtalY9l2RqMpatXqN7eiVCN6gaixsI6na0MZu/BPg5M/OfwEPP/JklCGfPPAA6xGZnepsUTViGxvEJElCEUoALAqwRMYe7Hfww+urUyF99vuYXXcJcY2Tjse3T/3bLC9lPRMwbkOWLV+JsJfE/muyp/TbDnw1Yr2//Oeuu+dEmTHp85/FrqM/ZAMWsbbIn7sZo0m7a0DPN+5clACcq/lRGbqTTlrA9e1l/5odd7yckG5zA/CZQ8fhH//h0uJuRx85ERecd0aGc6vyf5WejqmsPH3CAXSy6AZ+2BQ3kZpnFO4qXDfVkiXL8P1LZkWf/Y2vH4dEEndviaCBxllIQ1UVpP+B6rAP+cURcysAHwRkcqBR6e3XSbWDp2dKLK7httZrSwTHHjMJu43ZBS+9vBCfOfRT6MjQPXoLqiB8CUPIFAkTxDYkM/GI6PWiNjKj3dqMdIFas9nAjy+7GmvXvhXCuJMm4qBPHWDxcSJERGOWiREDzrgVy8b6YAXAHJBo9LyCyrCd3bwkz1l55ZNeLZY1i5KBUjT1uvvsvQf22WtPVcZj62IdTCLRwDCXkLa2lo1y3VmhyBT3htn51/UNihTucv69u+65Hz+Z9fPoc//+Oyeh2lZFq4/d23jNGHh/r0Jtg1N/2RgEst6TF/ZxTlIZtvOjEL6sdUBl+M4uEs4quqk29YKEOf5iRYqXHigKM9z1AlfdKLB7BLlUu8eQollT93CESVDbtUaFfqr+ejXGRa+/gW98M74FyZX/ewY+li0k69HS7oFC3UMT2i962A8At/gdRvNyZdjOjybZtXdGG+Rj7cCwDfMBEskwCrblSC4lrRuEmNmpZlpiQ3IsQmz/hcDvYUyL3JsEDmheuNFyP994Yym+cepULHr9zeB5J3xlCr7y5aONDRKkRbMWdLAsDiaWDMRrpd5T2BZyFI1E8HAoEHfmXhYA3k4A9TUvxXUgPX1PszYd6qaAoiIdTo+xhKnx11g9BWiW2JBmqlP+XptyDkoVn9GWAelKj2yIixcvwVe+djruvCv0rKZMnoiLZ5yDQYOqmo+md1A0tKBS+4W20L35xk5YzL/R81JOm9sLhlSG73KngC+KUVu7BJlICYyQ15VkMHar27WUiZeQ1NBnqVFPU2cP6LAGgkod+klHBAAUAMx//kUce8K3cd+c/4gY8QmYdekMjBzZkdmLNNroHNLFmyd1ej41+qUyfBcLCgIvVobvoiUEIHALSh9Ek06PVXyFD7flPaStTLGYuoteG6US0lSdwGFQSN/11v2P2VPWrOnBT6+6HmMPmIgHHnosErB+B9decTE6R3YEWsIVcsDrkydCGC5McwhsV5qXuL1Fpd+LD24CiMaaBUpKRiskDnZ7bi2udCuCXpmpNu0isFg3YXoCBzTqaVNlj+3OQ6ZHEGpPxGwsq7q7cfe9D+DwScfj9LMvCu79oR23w12/uwFnn34ihg7bqlC1LnHMMKDzij8MwYkgVsm1ZmX4aOddrXkxX003FTRXxH+60b3gFgBTAv+42DqaXqGXigcEQYU4Vc2UbXKid31a5DKazUaJUU9NgsB0MfkHIZDo6VmLZ55bgLvuvR8zLr6iNIN70te/jHPPPBnbbrt1trhStzevKPdabZWef6bbsnXlf9HIqnvp4/udgMAt1Y7RTwcMyfCN60FMaXQvQKVj19YFHR9BvXtBhjmHaBu8YmqRfC9393tYiiMKQLJFbc1GWlJ50lQtdS6wTNMmnn/xVfz5z4vwn4uX4OVXXsP9Dz6Chx99akCcfvp538aRXzgMY3bduRWFqx2OTLOqrubPexD9fc2p2pP0LqnayYGgmtEUABprFuRxnim1MQypDv/I7Hr3C3cQ9PY7Sd0O0koyLKlTFNXyBt5MbSNlBIPWAVyZhDSbDdfZSmfd/s+v/hVfO/lcbMzrf+z3UZx4wjH4zKGfxLbbvN8Laf30vIQZbhWpU7mstg7MgsXwAlTt5gvkjkrHrrNLGZJdeg2AifXu51HtGNNiVMcYNLqfj+7lJl65mTFjZJD11N+LHY5TbtRT51mJcw5q1UopA6YcOQGHHnwg9thtV+y44/Z4/9adSJJEYTdSBImm6lPElseKKuQQmx4CJLovvM+86ogxznZ0P5/f/xr/W8Fsqh1jbqt3z78VkKMCSKXQl24PVSoM3qZUWOyf5R+QAqiOVYHpc955px2ixK21VYpaYc30Y44+Ap/4+L7o7e3D4PZ2DB4yGO2DBqF90CBUqm1e1xxtMsUUkruOXvq74FG8lD2LBjLS7mFC+gfJMG5AiFurI8bctkGGZHedBcHkevd8qXbsVkhJffX8coRMrIvHYNnFy4cskAF8bsJ4vLl0OX47+x4AwI4f3A7HfWkStt66yx70kv+SCD64wwe8+3tZgzJ0T7Suj+Dd4iOiCNtn4PVhqo08c48v1zQA0Fg9P+dnNLVc2qhdXz3/xwDOqI6wJfr17udcg73Qw1vEqjJtEIPHMQ6Axfcntzq82BI8HgC67ktPOkU20PYs9kwT0WrJa4NnvPtWnzUCAfIF7eg3HwAurXbs9p0Y3QfalfRSgPPqq58LU/s6NaHtn78bDku6qLy/pdi5NAp2hCU+xbYVZWXkjO8oGj3LMqLSGI6HfsNNpLBQ11vFNtBsaRjOA3lpGdVLGVIdsftigJeARH31s/p9i3+SIXIYhZTLtmllsD2aj1HHOqPs6hyoEABBQjR67xgGzrCVLdyBtKQuLKdVwYzn8usuadF2ExnSuuEeN1J4uT/W6sjdVcEZwi1TVTbOT6HEFnywqklElbbxTfV+v95zycg9tQpSrrq5RepJAMpbBvW5J2E1iGGGYu7l1RF7DHj24Qb3fhdiJoB766ue8Zi1Z/leubQlqKKzuhqPFn+FCYKtZem1FdC9L2I3R9N1W2XVIfRtk3I4nFfk5aokIk30sHxVMFwdsYehVf/qZwDwXoAbPDBsgwypjtxzCcCLACysr3ra/yzOlMhGZSLw8OhU5bJgVr0tzEOxNRI84sMDo6A33iRsn71X/EDT3xjOQXxACrbkKOhWQwkzVj0DIRYCvKg6Ys8lm82QjPD3AZwBoDdkythIiluKNLuAIeHptZoppur9E1mqL0J94jcB2Q3JiLKdSIX2eCX6VSvQVeteEtOzhdWRe1ojvuppSOs4vRnVkWM36uDJjT7yqDpy7HUgLwSI/ghTWKx6tVJBs1GlS8OEXhn8lR3sWsGSAM/u4y5BuiOaqlQbnKUlOEdqEVEyaFLV7XBuYTpmZGO4sDpy7EYfOLnJp7TVVz51MYBzKEBt5EeteK58KtiIxk8DqcNoimkV0Yt4iQhzuIvapsOEJh7CYvZb8UMQlegpO2xBZ57yUz+NbRbTwAlIhBlP5WP7QXXk2L/fFPpu8iltBKYDuExI1FfOs+mNzo8GZUv0PC7E8AsoXLrYVFMXKqhVLS4l08r6pvbAruC0HQXv6g0M4LZGN8EevRPf6BXEZQXbOR8DZqx8Kl8Vl4Gcvqn0/YsOluxfOW8EgGkCnEYAtc69/M+9cv0IXgJ7JCSt07PB3ZG0pEWrorwN1iChGhzoFJE85Ka3EbQeQ9Wbd33lU7l0XQZgeq1zr9XvCENaD39yMCHTBDwHkMjgngyO3ALcMahBOj4gUHgiaKy0TOt0/1gv/QTxKrX0CZ7+8WSMbMxmFw9R69w7Ml+BgD8gML3Wufc7d/SqkYYVT04VwXcBtlc7PxaRpifjLUH+aZpeCkafxialGStnlBya5+1viJIzebxSZT/ID9NerS/4jACA+oonQUEvgAtrnXu/O4cTW6Y8cYIA51OwUy3ClPrKJ4KabI0r5GWqeaeReBlgRnYSFG1k843WVEQeoBTUx7zCgwsUNmK2oxJjY6ILbsWTEMFCgDOqnR9794/vdqvkifEEzhPBISRQ64pJyxPFHloUb180neoWpWq8IrtiD/j8FGiEjFJwjcLCJezPIsFV6wAAAeZJREFUkfJtCfVto3NZ8Xj2DLkX5EXVrn3eOwfcO0l4fBsSUwH5FkDUuvYpkajHvQHEQE4x+wK7t8WdzU69jZ6YFH4gIeLUItVmu4VqhHcUuBC1zvLxZ/e/HJCZta6PLXm7aPi2MsRJy2PHEjgLrQOwUOvad4OMsYd726RcsXewRcDLQFNvZ0OJTjiGtuSfDDxeAsA8QC6pde1z49tNuy3CEADoX/7YdhA5o3W4WEt7VEsn+ljJrp4wfqsgPFDYYFu+6iqq8cOgLuYblzGivuIxtWOw/ATgpbWufRdvCbptMYYoYh/cOmTMYfS1UfsOxMiiBTruWjmVVRx3WsCwHjroV4+Id+YuBdWBxrLiURX08FaIzKp17fvHLUmvLc4QR+hHJwE4EeDE3KuvjtpvA995BEEbnTA4fxcbc9Knuqa2wec+qu9zB4hraqP2u+2doNM7xhBF5MMBHA/IFK2caqP239jve75zuTX4i+7rNnK/BYLra137zX4n6fOOM0QRYCyAY9AqXR39lxDxbRiD/9aLaBWd31Qbtf/T7wZd3jWGeISZAOAIABMAfDh2zeYyKUL8/PUygDsB3F4btf+d7zYt3hMM8Qi3H4BxAD4B4ADA2wp981+LAMwF8CCAObVR+z/6Xpr//wWa8dQR4CwJJwAAAABJRU5ErkJggg==")
        b64.append("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")
        b64.append("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")
        b64.append("iVBORw0KGgoAAAANSUhEUgAAAGQAAABkCAYAAABw4pVUAAABhGlDQ1BJQ0MgcHJvZmlsZQAAKJF9kT1Iw0AYht+mSkUrDnYQdchQO9lFRRxLFYtgobQVWnUwufQPmjQkKS6OgmvBwZ/FqoOLs64OroIg+APiLjgpukiJ3yWFFjHecdzDe9/7cvcdIDSrTDV7YoCqWUY6ERdz+VUx8Ao/xjBAMyIxU09mFrPwHF/38PH9LsqzvOv+HINKwWSATySOMd2wiDeIZzctnfM+cYiVJYX4nHjSoAsSP3JddvmNc8lhgWeGjGx6njhELJa6WO5iVjZU4hnisKJqlC/kXFY4b3FWq3XWvid/YbCgrWS4TmscCSwhiRREyKijgiosRGnXSDGRpvO4h3/U8afIJZOrAkaOBdSgQnL84H/wu7dmcXrKTQrGgd4X2/6YAAK7QKth29/Htt06AfzPwJXW8deawNwn6Y2OFj4ChraBi+uOJu8BlzvAyJMuGZIj+WkJxSLwfkbflAeGb4H+Nbdv7XOcPgBZ6tXyDXBwCERKlL3u8e6+7r79W9Pu3w+hMXK5G/JDsgAAAAZiS0dEAP8A/wD/oL2nkwAAAAlwSFlzAAALEwAACxMBAJqcGAAAAAd0SU1FB+kDGwsfKMmdAyEAACAASURBVHja7Z179G1Vdd8/c629z/n97vslYCCKEN4gIo/GkkGQRgOoCY1iHdGMtCQjHUlTQ80wSBokqJEahwatGemwo9ZGHY2iiR01aEYbtLamraK8jFrQCAoGjdx7udx7f49z9pr9Y62112Pvc7nIs0l/Y+x7z9lnP+dc8/Wdc64lPM3+VPUc4ALgfOA84JjH+Rb3AZ8HPgd8VkRu4f//DZhwsaq+R1W/rgv+gMe0HeLv6+HeF/9dZ8IZqvo7qnrX4038x8Cku8IznfF3hxFOL1XVjzhVVXWBDu4xjnSnj1WyRv4+oqqX/i2WCHeZOr3J088dFrH8cS4jekb4/rdsc+WxTl12iuvPOaz79tfSm9S5y/42MeJC1e6jql1PqMNjQiJg+r/LGNBpvKbLf++J2ZWMKa55mM8Sz3dO1XUfdc5d+P8wI7qjVbt3ONc5p55Qi17cuS4QM2zh+ET0SOguEbU4Nm2uPyZ+d+U18++Rse7Qz5fu2zl13TtUu6OfKLrJE2MnuleDvl5FzhQFMXbRceGdw6NI/KrELwog4h9Us3Pjw0u2Iz8gez1FkYWvqtknf4w51PP6x7pd4e3G2A89rRni3PwokKsFfa0CxjQLXmyeCFrxQPTwniqxrLyOBMJKJHR1PU1cDwSQ6mrpfDnE84ez363o9cY0DzztGKLd7IWI/JYqFwEY24wzQkGkJmz4VwFRRMWP6vzAfCSr9AIFClpyUjVcUyR+Sa/b014zHmSSVIudCjLyLq6bI6Kg3IzIW8Q0n37aMMS52RUC16AcK7YdefhZGv1k9Is00nK0a0YPkcEg73nQn0xF80zaVNJ14s09DzSpwezmqhIJXfIFMCPvpm4Gyj2IvFlM876nnCHarV8N8kYVloxpxyQnMEDROKoVVJJa0cABCYTSjKpBVgimJAaVGQ0lWJpK9cTrV4MgqTOprIv2TE6DpTzf25fJOFNgFfRNYibXPyUM0W59GbhW4Spk+KDarVeaOd2wIF8a5KMPo9mJGX3K6y34LRJVVEqpHJGmNADGbVQvaURpmVRaYN0PGOVtKlxnzGTlSWOIdmvbQK5V9EpRQZqKGfP1JA0ZWTUzouXoZgEhPMVUxh66NOm1WSYf+cWdyiuUrptkz50/I9X5QVrstGLKWny/GxSuM3a69wlniOvWloG3gl4JsuChkueU2wDNDWWuLno1FY8fuEaFV5wzWnNDnSskpWCkVE6EDoaAV6uIJBu00P9KQmWa4fuHQ29A9DeNXXpUkmJ+APm4FrgSHRkh8zVvK1RBFRENxPXf/cc8vgDtLb16xmhOgnCd3taov374nKTBX1s0+x6MtvQ/ayCoesMdrtWPnOBZaM9NDY+Ux4jpOpHqbr42LjXClQLXPlrqmkcnHStXg16FKqZZqpix6gkqfgT2tkHTa4BDcCmgU01boT4Sk6KEoS5IUvpdVAtbkTPI09r5O4smlRMIrpKpoN7DyogtSU1p/EczOxIYKKLofGWEKYqqXuXmK1c/ISrLzVeuAH4fWDLNcv3biALIXPzCqheWdPAvRewuqGgIMaQcxZWV761E5Q5T2Q8ZM9jxGKGPgcYdkMymDTwWGRmkK977Ev6Zscvve9wY4uYHXyjwPkWOHTBjtpIFZfmLSKaKSu1fm2OlDADLK1H9lnR87b8NXYTcXmjlIg+HTxbfJ1snilI//wjLguSZZkPl4Kyg6D3AFabZ8OnHzBA3P3gU8CGUi0y7ofrtAIU7pVVgxyF83pHdY8GgZsfX38egkUXHjZ47er6kSJD0LMOItnr28JsoyIBOB0NEz6tNs+GBx2ZDVK9GdZQZkhnAXp30ajyzDaJJSMgNZY5lZYZTkx2Q7Hq93tYh0ijRMGcOQwHaqg45MdilgCsCo8Ku5AZdo4MQd7lenbn5gZLIzQZAL0L16sckIW5+4NUoHwQw7cZMTe2v0NkFV679z1HdyyHE5RCSNQKPjB6rj4IC1TXyoPWQz7ngfUqaHYjHvsY0Gz/0qBniZgeOBv1T4EzTbqqYkb/wUB9HqGT8bavbS47KSrI5qiMRxOFQYgEnKmfi0NhAzZGRay5ieEEXZYR2twMvMe2m+x+lytLXoSUzkvbQPH0zUA0yyM664VDL1EOvFjSLScbUxIACOkITHWW+an297NnC/1q8B5U7rhzGbbL9OiIxmwDOBF73qCTEzfZfiOrNCGLazRWHtUBcZYFhHRvEBZxSCUY6/lA+WO65jYBSUns+IfKOEP8AZmYEgpZkv3LAbcz2DIC0SuKjOzwZSImCXmTazZ+pab8gA6O/Ciqm3ZJdaF8iTsxb5O5PIJQiPfxROLlCn/nIT5n91TfZ98H/BP/nXpqHHqY1BttazFSQZx4BL/5x2osvDCrA9XBLSf/S2HoCugCDaA/PIIrrHAdvu5PVW7/M/Fv3Y7+3B5mt02zcgD1yF+3xz2JyxqnIKSfl8HLO3wxIyJAzSRKuKlk20+HWH8ZMNvdS4tb3iYr8KvCZR5QQN9t3GcqfeM5uLhgyJqKFd14EanEQZjB4eKn53r3cd+X1rN+zB9SxjGOjcTSiNBashcYqVgRjAGOYb9mC/s5v0Pzw0cPkh0RgUDNmlfDsfN/DfPeDH2PvR/4L9vv7aawwEaGx0IrQGGgaoW0ttm0wR+6Ai16A/ZmXotu3jua4Bpogsx3FzyLYXNOs74tB6D80k80ffwSGPHQTyiVmsrW4QKletDKU9ejXfnTmqKubzbjr567m4e8cpHGOJXEs07FBlKZRrIHGKI0JTGk8dJ5L2foxP0Tz7rcg1i7UkXkWEoHv/cc/4Tvv+ijd7v20BiYGWoHW0jOlMcJkamkmrWdIa3wtwMYluOTH0VdfDlYSuFhoVu0HQZm/L3W5mWypafpJM9ly6UKGdOsPXSrwp/7knCEPLYrBRqDvYTAmAg/9t7/ga2/8IE6EycyxpHOW6Vi20FgJkiE01mGN0ojfP2ZMnbV0119Fc/IJA186f8bZ7r1869ffysN/8U2UDsHRiiZmGKU1Xjom04Zm0tJOGkzTIK31qdvGgBF05zb02ivhyCMGWEBkiOf/UEKkZ8iQpsBLzGTrTQsYsvcjApebybbqxMT3Atyr8hURc0p6259x/+//Id/86C2gynTeMZ0HZoijaSxNEyXCBOlIUlJ4LIX3Ylh58Y+x9Ms/n+xpBDVUOPiFL/HXr/09Vveu43A4ndMYRwOJKQKtUdppQ7s8oW0bmrZFWs8QGgvGghEwBjWC/vavwXHPrnJglS3NZDQBof7Z7HRbLgAAN9rJ1lcOGOLW9pyByB2qFCe5tb3JkZAyN4GOqvJijDzw72/k6x/4H4gq7ayj7eZscB3LrsM2QtuaIBmCbYWmNb39sKZGhStR7DpWnnkES3/w1iJxvuc9/4F97/9zVg+u0zkXHNo5Tc8IL4GtUSZWaJemtNOGZjrBtA0yaaMh8xIi4jcXXOPfvRo96sjC5pMPyiG+mUlJzpC9URM/10y33VnEIQqvomJGt7bHg26qJeShZT5Ce3wtQh6egPu//DW+8Yf/HRXBdIpxjnbuaOa+Hqu3R6KIFUQ8B0Qs0rbQNNCGrQnqI1p9I2Asy9/5HrPLfolu9150ZZWHf/ENyAf+HJl3PsQIno4VzTZoxDO9aVsvmROLsQZpAiNaC00LtvH/iwGxXiv85u/CfN57WoKO5E3o8y9Cgn48Tf2fnWyLKPOrxiTkLkVPsNMdmXTsKcKDvrxmAbpXg9xfuPCfs9q0mE5pZnMmsxnL8zlTgnRYwTaCbS1tK1hrsBNDO7HYicGI8YRQ9fkQVXAuuZxdB+szWJ+j6w5dd8wVVjrDvlXHwfU5nXZAhxEXJMRvExHaSUM7ndAuWZrJ1EvGJDCgZ0i4v+vAhfu7Dn3uCfD6XxlHbOoQpzrGTrdXg5677XT7ib2EuLXdFyuckAOZ3druLKDSPtIdy51pZU4F5d43/2tWG1+FYlxH4xx27rBd12fyYu2VoD7/JBIslSA0YIPqaCd+m0xhEj7biR+9YlG1MAeJzHI+LjDhBU343ORbY73NaAxN0wbJiMxo072NBWP8/xLUlxHktrvgW98OA7TMiqomraJ5fBS9zbXdRXoA9IRubc/Fucp6qahilnYUB0az1NcpZRCHVhm+In2q8MB/vTswQzFOka7DalcEvdEpiHkH6mDS54lLprQTP4rbQDxsklOnoAYEDBYxwRapYEnqyhpD0xpsa7CTJqkpa4OKamASVKZJTIjGHYLU/LsPpwzwICXtM5Y9LSWqN4pyCTPdEWn70p4hil5c11RoGMG9rYgQ+hjkrVrc5Dsf+BjrrQcBxLmeKcbpIBFFTO1q8NhcBq/nqVMT1JeZ+C1Ih38o04OcgmICWmDVYESx4mgEzwxRmtZiG4u1DcbmjAhGPP+eM0FMRhyFr34D9u3L7GyOyYUYTDVjmo7UrkRi+g4u0609eA5wfO47d6vf7/McknkPqi7lQIa1IQEshL/58Gczl1AxXYc4LXLgvbPktFdffr9DtUuYXzzHBS/K4vV6VCPGS0TEkyQUV1gDYqQfnVYUiwY322CbBtPYSjqiejJ+qEaGS+CmBBvSOXAOcSCf+Z+lu6upHiapKZecmMDQbu3Boh4A5fhu7fvnGFQvQBW7tKuuL0soaSYBGkeDpP2SV36grOx3iRnOIapY57LnrlBdrTbnEHWlIS9eWIO0mAz4kwJACE4YDWCRoKqExjY+Em8spjWJETmT88o4ExjSOe9EOJe2zsGtf5no0z+bFoVKSdgj7SjQbzvdFd/tAiNwvgxTZ4XJFqjg87JSpHD0VJk1DRme50etq0GFNGJ6INJpL4Wavzjes+kZ6CLVTabTk78v4Wcb6GkFDIq11nt11mJ71WTSdSRnsAYmAHMHncK881sXNtch375/iL0rI1U0WjBoHHrX843izstp3a38TYmrRHUiZYlNrqJS5K4c/Oa9qKTCs37LSgX6isC+3ldQF1xblzOjC/sCE7poTwLRrGQRmRQ1JEYEYyTYEMVawTbWS0ZjPBZmchUlZVQW7z+fe+LPZ4ERQVLmDuYd+t090M2rom8dlmloqUVQLWgdHKXzDFr1gQsFNyUvQ9QUyBU1Pj3sDGvffmCg+sSNVDEU48pl13doVFe5atAuSEpuV1zS8fkgILi8BoyCQTDW+jjHWqRggs2YGeObEOPM5p4R83mQjnnaAnNkbQYHVob1AbEera830GFaTWqtwzHNoixcH5FLxoACN3N9ab9kOQl38GBwPR0S7IcUkUvIl/TQfKYmowusgjrn66C64Ha58BwmqBEVcIymaSXEHlbBiXjb0ZggGYLJ1VSeFHMKdCkKjsFn5zxzoqTMOy8V0aasr4JsTDQSxjOMdaSoQyS2AcUuH1nxQwtDKZJLQlEXE+6dctDNzu3gvJfSQyFeiaRASNMDOjXYXi2Kt+OdJgOEA5mnXIPRMhZAMt0fynCCPy9ivNqyFjGeEcZkzkAmWb30O0pnouuG0jHvwM2T9E6mAVCVEftxOJUdYJeOoFv5Ho0ubgBIouZGcq8jiWRVZcNxP4w4i6jxtMR7TJLlRXL4RXKELiCTEbHt79tFfijiQsyRAY6+njjG4g5Rg+Bd3c40wZHyzBCx4MNEfy0j/fVxqS7YE1uTzZh16HyOhM9enc7R1sLyNMVOsoieY2VHw2ObIv5YeaAs6M9qoMayZHWyTATandtpOuiaJgxyh5guA+BMLw2igjjfvIM6NDDAe9TGMySMuh7GMcEoadjvDEKDiANpQLsgjYKhw9g2BNweGxPTeGZEYKW/T2oE8tKhmVGfo7MO6VzytJzzknnKc6CxlUbSzCEapuRzCLhbeQC7fFTKqcugEiQSKFrkyHgpUP4cbo51rxrsRSNK5wyiHmcS2rICMOTj+3raoGR8a4F49zeooWARvCRF4xP3K+AsqO1zJBJiFKPedmgIbj1QqT6ON9YzItqhvEZCg2Q479pq52CuyMwVbrDGYOfk4weFF3XhR93mWGNbebDRFPGFMKgq79sD8janqpsoH10KLG0VZnutH6WiuGDwTQZH9yYitChEHZxaDQSHQZzxtsglva+YXpVKXw3ZeI2DglqsCGqCZAd71oOXLgSAnWQNpJkX6Zy3Y0FlydyFWMR51RVtoxrcWaf2jkRZkJIl37NkUl92JkPtJqplXZZmAKL2PnOmkvpcSB48JiAyiuqunzkLUT9ynTYejdU+ZkbUoGpxWEQbP2rVBgL737QzqPPH47xa0U6899upd4Y0SJZaf+cQ3Bm8OjRYRBpEG6S/h79PRPT9iA/bzMHMoTMNnztkphC+6yzYKrVe+qdTOP2kKpCOtHHBnmnhYclIKVtVKFca8SRJmgriMoBds6I3qQxK/H7Uz73UR+Ya9LVpcaZBpAnobBOAOhtc32BotcEFFaQuGF0XPC8HdMHQO0m/9UPGqyHRBtSgWJ9QEoMxjU96BbuhaqALtsOBdMBc0S4yo4OZQ+aBEfOw30Vm+PvJZT8KmzeWdjTz9CgQ8DTQJXOCtMq/N3XrRoLDJclAnrYNVlczNRY7atOxhuWlFVZWtqBYOu894HSOiee54J5K8DIlxfHqwNjAiKAecNb7smr6KN/HCeLtARYjKRAQLCaMUy8d/no1utl3ebmgVjqXmNSRJFJsVt4UJOwnXpD1xFOpIymqPLRX1ZmKFBnEgGZgL4Qi2SK5GtTKjcsL5CT5AKAc8U9/1Ov6oLacBBVGkBo1CDaoAAlVpQZ1BpxFOy8x6qInhJeMSKRwnPe2DIJBxaLG9MEnapEocWq82nTedjBXf625wFyC2lKf6JrjpSViWEGCQ1bFP+cLjkNPOb40ppJ3yGkPDaFaFIgoVfIqZ8igLlY1w+1zsaoQ3gwSkCJv6Pcd+YoX0egaThqQBkeL0niGaMj0EYgZidsZ6CzqvFpJNiOqKoN2Qd1EQjrPnJ6x0VaowRQeVVBRGjfrJcZpsiMzb7x13nm74SRjRhPk3H/n5S9MaiijQ59Dj8BsBccrMW4itTNkQmtK/KG0MmW3K1mxQ95RmzyEVDfmH2zHCzb2QZiKlw4vMTbYikAojYbWBI/L+JgkSIcGAtJJUFEhog5SkxO5B9w1SIqL8Y5nvnYCXeMZENXRXHtVRbRVWB/XSBg8Mb+PRU85Aj3v9KLfqqzPztDdOGBVi+4rQbMahaShzBjkUhgjsmgYCumhyq3XMPOxb/0FH83imaAmqA8aVFtPQDU4FVwgXPSocIJzBtdZ6GxAeiPmFJkUjscEApreuY7XTte0aIeXxi7sC1Kmcw1Sh9+n2WCJ146bWPgnL4a2qYrcU8dwby/QbKDmDXOaSYweysvqk9NVV4CWUyfF8hctH6TuvDCt5YiXbcGJoROLk9ZLCwaH0LnoElsMDQRXVzuD60yvrpLNEO8OdyBRWjIp6V3SkOnrex2jwXUSvCvCvQw6F6QzPs5wEQULXhqNtzv9ZnHPfyb8/TMzPeOyNK2WGZCsHduj2N4d7rWIjNgQWdRHoGWCSslh90wcY5txBTtHQ//sq1+DMQdDdYgJRtHbERcMvgQmKcGz0hCwOUGdeMIF4tElDyiqF3XSM1bwMY+PZ4K0dUFlRSdgHlWX8apNpVdPGraoquhVVWDSL1+KWpP1wmTp2iwFkOq1Bm5q1qtSJv7EG/W0o9n0w0UiqveXRYeNKFKJXF8METJ+kvoOj3/Xi1CgE8vcWJwaOrW4EBP09gLrX7yPM7yBd9GziqM8AIwa7U4Q9IguoynWECfpnBhcxlgmel60QBukwgYIJqmr3gb+o9PhtONH8bwiFS066N3p6aFluqHZ9KzCUpshbj/SIKlknUYjyKUmz0Ji+YsmA7/17JPZeekUJyZ4WhanAi5IiXhXWF0MCBvovF3x6krQedD5UT1FYx7d4eAwqPgNbIBKYoOU+qyki55YqtLyAWyTHIK4n7Rfn7UZueKSUrdLZmelTuHqIZpOx8vWI6LHfP+94+j7AEHWEZeiKoLQanq+wOBnX/Ma2i0H6TA48YBjJ8Yzx3kYxYOIXkW4EHlrcHU1AInqMle4y6L2zIZEO5BgGvGjP/wm2oRgzYaIPjKjRaQNXpVNKguDvOESZMvGqhN3TMWPN9qlE9wo9j7ff6+fO2UAqIgrSleK32PCKEeCC4fAVUUQrogsT/nPv4g20NHgxOA021wMFEMQ54Ked6a3Iy7A7cn7CQFhhEMyN1poAsbVBMbECN6ExFsWUwQpENpwTvQAAwb3a+eiZ55YekR1H2Shn0b6GXN1pVqdn441wH2DXGJtdGo8WSiL2HJIXpS6+DA+kJ22nPTBf0DXNqxJE+yIDxbBf++jaqIDIP2+aNyTa0xvD3omiU9C9SM/GuWwaWBgnwuJLm5wLKANdmXiP19yDPqKC5JDU9cV5FX5xbtXjJA6oaQjxl3vM6Cfz/nRbDq2LHwjwqKx4JkRvZlVwVd1wPlMOwgsHXc0R1/zHGbNlDWzxMwZ5mq8KiN6NUmHex1vUjSeMyEyJw8waRLBSZF2Vunbxyyxoh3JJEWikW+YnbQVd+VLQsF1Rg9ZUObTM8iNTFJQSYVAu/k5dXHE5w3o58Z0nVYlRjqoMslthxapWSmmVdJCTAV4xiXnsevlLbNmyrqdMlfLums8VB8Mq4pHaDUQLaqlaGtytUXhbcWIPaki7Q21ycqZY22KrTYvQatbN2GueRFsWh7mx3XMSC9owBwwbfzYQLvPGeCzqDJ/+K8Gdbsa/eh6LqrRXL2WU2To4uIxVXjW617GrpfBejNl1S4xw7LmDKvOu8WJeE1vfDXkM5KdCbFK5abGUR89LumNcyK4asC8CskxOG1Y3bQN8y/PxjznyNheUvSx68BI63A6kcIrdSN8SleZ9bTXz5pm83G3IPqNnMrNluOSKxsqujWb1CvNClYns/JaIy1qGns/PEqSwLOu/mm2X7DGqp1w0C6xKg0zZ5nhpQVK1ZXilBC/xBRxNMA5wTNQkOASx5gieXOSOZuGmZ1wYNN25Mrjac8/MUuKZ9Wvea4o79knBsg61FS53Qjfms3HVUVy+o1m83G3mHDsp0YnZ6lUz2Cmg0yCqgq8YjqrshwpQdKK49jrX8G2sw8ysy2rdolVM2HmGmYYZpgE6vWj3kP5Dh/DSG+UJSWm8qhdIn5mE5MkMTcyY22ykQObtjH5lR9iesmZ2WAP2T/RUEET+ViWM8WZ9CQk8Tz0XkpP9AXq0t2QFvlU1h+in1Bgtu/r4zpQSwcildbnEwRkXkM2gkQrxirFRL2qyvHvupxt56+ybhtW7ZT9pmXdGWadZaY57J1/NkW84CGP5FlJ3B/yJDmMHrGpCN+sTLdwcMMWpq/ZSvtTzx+xf1kMWEMmPYSeQUxZ7knQujmnUFfzh78e7/eJAmGf77v7LuCEZssJSbftu/uQc6aXPVNA0asro03Twxg1HXffDX/G9/5YmKBMu46Nbs4U5xv7xdFkc/1Gk5xy+qnKOsUaLptrhaLQG2BuW1aXNrA6nbL5NctMX3mez34qlNOWlT34Y285mK+e4XRncU+75UdqGt/dbPmRE+umzxvHp3nIQHetofe8gjEZMEWr5pQwB6LqSBe39p1Gx1z5kxz1sw1rpmG1aVmxU1axrCOsa8NMjQf+NE8Ymcw2xKKJ4OZGydAsnx6OX5tsZP/GbRzcsMzWNxzF5JXnZckjHWiJVMiRHJ66oa+wINUHqbrSqi73Gwc5qPm+u88AvcMb9RMTBx+6q58PvR8bBcKbTZwn9Qxw2ZR6mrcfSJnWlHLmxb2fuZNv//Z3AWHZOZa6OUudb/pvrNBKamQTyhaEMDNl5mpn8Hg4Y2V5mZWlDaw3jp1vPZb25KP7mbDLZwt1yKp9OW3yZKWf+TSfHTvOdYJU0+eEB2i31hpIUZXntltPKNuimy0n3Ily42CaKaqpVEuFmgRSyoCdTCLIquh1pOQyGstoX7ZdeDonfeAMsDNWTcNBO2GlCYa+E+YuZByjPcjcYu1jFNtn/TRA6fNmyv5NW9i/YQtu84wj/+A0Jqcc3Y9eDfCP5BPKZP2BWlRpahaf5RU6WaMsmS2V8fyHwo2RGQVDQn7j/Yoyf+iu5AJvPal39aQqgBiAjeHGWn2OakCrmESzFyuT/sr0mGdw6h+fj5kcYM0aDjQTDrQT1tSwpsK6+ghfJbm4xf9FcGhYnWxg/4bNHFzeTHPCQ+z6wI8hR27NHJHUR5nPNVwkmnK3P4+8s+IOVc1KSbUor8o1z3zfXdFLfX+VMUx/7ZaTbgI+OayGcFnco5kBz4noMuhLC9heK1uTN9prMdEx2W9gt2zk1D+7lM0nPsSaEQ6ahpV2wjqGGTBTocsCQe9VZTYEH+kfXN7EgQ2bOLC0xKafXmX72y9KTT95EnpQWVNXtWVtGrnLmllMGQyukSnN6fs1P9lsPfGmhQwJh74XlNlDX0uM2npy6QZmpkzQwYuN9WbX4VFpKMtuXq264J/zb36Ko68wzI1jxTYcaCesmJY5hrkTZlmcoQF2RyyzZsL+5c3s37CJ9ck6z3jTDjb8/N8rcjdUMZao9pX6WsyOV07e2Q8cpexVHzDPS0279aTMLn8tpireW1N/wJB268kfB/3Y6Iw/fTuWK7qmCvggZ4+MNANlEpHAYl28dFGQymf87Pmc+uGzaDc8zEFrONhYVoxlPRSMzJzJgETLervE/uWNPLxhinnmAzzzj86lPe2YcsCIlh5iP7NqDpBmzyzD4Fe1Hvkjg3F8CqWPtdtO/vi4Z1v9zfZ+5UJEbgak3XpKtv+rDPuah30pMuz7ycqHqlKIwbSi5VQeY3NW3n/Np3j4f22ldcK0UzZ1YKzBGqGVhllrWJm2dM0KW66wLF961ujcmb33qAu7MAua6qHm3xxMqpZ8zJyG871fJcwCdlGz7eTPHBZDAvHfAbyu3XZKuf+hryTCZjO4UQRQYb/IgjLbuwAABpNJREFUOGcWpTHr3sUxbgfqrD2wl7/+hf/N+vpOGrG0RjBNi04b1BqWl+9lx7+9ENO2ZW+jLm5QyicnS8a7r2XPV0daMFuplIyTkhmefl8FeGe79ZRfH6P7oWYlfSfo7bO9XxlC+7URlPEKrVGDOPJdsmh6vLVIB51C0yO3cuwnfpKtl68yb9fYv9RwYCrM7F52/IZh1/t/AtM21JMfj+v6ygbq8HnKVR4Wz5iqVXqiGuSgejuq71xE9UNOpDzb+5d+ImWBdttpaf+er1C2CDFYmGvxxISHOTPxYJZRGJlbbyh9OtIxM1z3aHjtMQlePE085ZJy47M4t9tOzc1APPk17bbTFk6kfMipxtttp31IRd9d07DdfmrC+KXOgZTBYw2hLOxCreftlREDL2XMo4vuqzpyTQZ1Zb0UaLYkRp18WjRtcL7uychEATkzMul896GY8YgMCfe9Hrh5tufLFbNOH5nwmGHAFJFRreqWclw+m06grK7Pe+AzNSDZgjFaliWpViU5leemtURIqlfuz5MKq5JFRQshT1RNvJxrE4D1vV8G9GbQR1ww7BEZ0m4//QHQtwD3zPbcWf82zpQ+eMqCSKldQNe7tDnRVOvCvAhnaFnKOvCONWsty11VLUdz7p5qDRJmYGCdkKoQhlpQ4p4BM/Z8GVHuAX1Lu+30Bx4zQwLhPw36ZmB1yJQzqNJPGRCpWRuclkWvWeSuWk5FIaojbWKLjH29qFjlMBTFBVoUPBMbaCqoZJgvHyK8Y4hvu/300gbvuRPxy+m9ud1+xmEtPHnYSx612894H6pvAmV9hCnaj3otKhmjPZAKhqm9MuqRPYinxhCB2nNz1UQ5ixyIODORy56nBoxcmRFVzdrWkmsfB04amIkZ4Rne1G4/47AXnHzUq7TNdt/xr4CrVGCy/bmleO6+g3r28UGOajAfYRa9SLVAUbG4Szb9bOHQVBkWLec9LK+Trf2zaLGFoupSBgitZvPHxwTUkBl3xGd7W7v9jDc8Gvo+6lXaFK4DbhBVZrtvL36b7HjuoGxJK4+rTI9mi3XFvDR51Tip8qVfTCxBMn5hL1cu2CXD9IFI6Whk3djUrXlpdogRZLt/joQ3DJix+444Km5A9bpHS98faGHJ9d23bwOuFbhSgcmOM+vfh73sVb6kXhJybHGBQ65OJJUny+KVi6QObcYjmJGwaDifff4MbfXes913ROm6AbhusuPMvU8KQ/zNb1tW5FpBrwIZebjbBktuQVoGlUIPjxFouCKojJSW5Tq9XtYrv4MMpiOv5oiHYvmwkTVHyZelnOx43sj7CoK+TeG6yY7nPXlLrxbS8OBtV4vwRtCldsdZI9J023hLUL2aZgXB5KuxLV6aJBmlNKO29q3Hh1yTpypVrtPgQ9jLn1AzAmD24G2osAq8abLjeU/N4sQlU269QuAaFY6djDBltvvWQU12vzJzvrKAlGM39cEPHQPJjWyY/zdfOLJe/RbNl3klg1LIJDeW8EiGtyc9NzrgHrwNEe4BfXO746ynfvnuNEpufaHCb4lwkSpMdo5Jy63BqMsAVspzDckjGhbZEct04irQY9C/5gVo2QQ3dcpGFhQrVTZj9F0e/FK4h9yM6lvanc9/+ixwnyThS0epcjXIa0GZ7Hz+Aon6UvUAMhIHSAaNlImSfm32wFXVQdJlKCEZFqjZcg6Sz2aa44+iTHYsfv5w/XeDXD/ZedYDjxcNH1eGJGn54qsVXo9fAIvJzrMfkTHl4t4lKCcih1gZdDxrQpGZGc05Lci16SM8rwLcDvL2yc7nf+jxpt0TwhCA9e9/8WhEXofqv4gzXbQLX/SLw2zjwNetxny9kufIchoaZpZO3a/1Sp2lb7yIEbMHv0i2mNLvgb5zsvPs+58Iuj1hDMmIfaFfZExe3geQu84+FCOD6tAFrlVSWf1yp0jW25i5SYNZxKo1d1VoD/UsD96S52c+hsh7JjvP/swTSa8nnCGJ0LdcBvwS6CXRq293nfMI53yBQRud6GD9XQ5npc/smMkj3veW/DqfRHnvZNc5H38y6PSkMSQj8qXAPwa5PFdOk13nHu75le+82Br8QNdNhRc3Irx/svOcm55M+jzpDMkIcAbwKuBy4IQfhIiPwzPUu+7GF53/0WTXuXc+FXR5yhhSEeZi4KXAxcDxY8c8ViaNED/+fQP4FPCJya5zP/VU0+JpwZCKcOcAFwDnA+dBNRX6Y/+7D/g88Dngs5Nd597ydHr//wtISyPd6krIXgAAAABJRU5ErkJggg==")

        for b in b64:
            b = base64.b64decode(b)
            qp = QPixmap()
            qp.loadFromData(b)
            icons.append(QIcon(qp))

# QValidatorを継承したUint32Validator
# *** Uint32の最大値を設定してるけどpuredanbooruの最大値にしてもいいかもしれない
# これを呼ぶのはreadINIを通ったあとなのでparquetから呼び出すことは可能
class Uint32Validator(QValidator):
    def __init__(self, minimum=1, maximum=4294967295, parent=None):
        super().__init__(parent)
        # 最小値と最大値を設定（デフォルトはuint32の範囲）
        if minimum > 0:
            self._minimum = minimum  # 負数は許可しない
        else:
            self._minimum = 1
        self._maximum = min(4294967295, maximum)  # uint32の上限を超えない
        
        # 最小値が最大値を超えないように調整
        if self._minimum > self._maximum:
            self._minimum, self._maximum = self._maximum, self._minimum
            
    def validate(self, input_str, pos):
            # 空文字列は中間状態として許容
            if not input_str:
                return QValidator.Intermediate, input_str, pos
            
            # 数字以外が含まれている場合は無効
            if not input_str.isdigit():
                return QValidator.Invalid, input_str, pos
            
            # 範囲チェック
            try:
                value = int(input_str)
                if self._minimum <= value <= self._maximum:  # 設定した範囲内か確認
                    return QValidator.Acceptable, input_str, pos
                else:
                    return QValidator.Invalid, input_str, pos
            except ValueError:
                # 桁数が多すぎてintに変換できない場合も無効
                return QValidator.Invalid, input_str, pos

# クリックイベントを追加したラベルclass
class ClickableLabel(QLabel):
    clicked = pyqtSignal()
    
    def __init__(self, parent=None):
        super(ClickableLabel, self).__init__(parent)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        return QLabel.mousePressEvent(self, event)

# 1,10,100,101,102,2,...のような気持ち悪いソートをfixするclass
class NumericTableWidgetItem(QTableWidgetItem):
    """数値を適切にソートできるようにするカスタムアイテム"""
    def __init__(self, value):
        super().__init__(str(value))  # 表示は文字列
        self.value = value  # 実際の値を保持

    def __lt__(self, other):
        if isinstance(other, NumericTableWidgetItem):
            return self.value < other.value
        return super().__lt__(other)

# 機能を増やしたカスタムテーブル
class CustomTableWidget(QTableWidget):
    """キーボードショートカット（Ctrl+C）と詳細表示をサポートするテーブル"""
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window  # main_window インスタンスを保持
        self.preview_windows = {}  # ここでウィンドウを保持
        self.has_previous_selection = False  # 以前に選択されていたかどうかのフラグ
        
    # mouseDoubleClickEvent
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self == self.main_window.tag_view: # 操作画面がtag_viewか確認
                self.send_selected_tag()
            if self == self.main_window.detail_table: # 操作画面がdetail_tableか確認
                self.show_preview_window()
            super().mouseDoubleClickEvent(event)
        else:
            super().mouseDoubleClickEvent(event)

    # keyPress
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_C and event.modifiers() == Qt.ControlModifier:
            self.copy_selected_cells()
        elif event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            self.show_preview_window()  # Enterキーで詳細ウィンドウを開く
        else:
            super().keyPressEvent(event)
    
    # mouseReleaseEvent
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.selChanged()
        return super().mouseReleaseEvent(event)

    # 元selectionChanged
    # やりたいことを考えたら別にマウスリリースにマージしちゃっても多分問題ない
    def selChanged(self):
        if self == self.main_window.detail_table: # 操作元がdetail_tableか確認
            if self.main_window.auto_preview.isChecked(): # Auto Preview？
                self.show_preview_window()

    # セルの値をコピー
    def copy_selected_cells(self):
        """選択されたセルの値をコピー（範囲対応）"""
        ranges = self.selectedRanges()
        if not ranges:
            return
        
        copied_text = []
        for r in ranges:
            rows = range(r.topRow(), r.bottomRow() + 1)
            cols = range(r.leftColumn(), r.rightColumn() + 1)
            copied_text.extend('\t'.join(self.item(row, col).text() if self.item(row, col) else '' for col in cols) for row in rows)

        QApplication.clipboard().setText('\n'.join(copied_text))
    
    # 選択されたセル(の行)のタグをメインウィンドウへ転送
    def send_selected_tag(self):
        """選択されたセル(の行)のタグをメインウィンドウへ転送"""
        ranges = self.selectedRanges()
        if not ranges:
            return
        
        index = []
        tags = []
        ranges = self.selectedRanges()
        for r in ranges:
            rows = range(r.topRow(), r.bottomRow() + 1)
            for i in range(rows.start, rows.stop):
                index.append(i)
        for i in index:
            tags.append(self.item(i, 1).text())
        
        # Mainwindowの最後尾に入力する
        for tag in tags:
            dellabel, entry, label = self.main_window.search_entries[len(self.main_window.search_entries)-1]
            entry.setText(tag)
            self.main_window.search_entries_editingFinished(index=entry.index)

    # 画像とタグのプレビューウィンドウを表示
    def show_preview_window(self):
        """フォーカスが当たっている行の ID を取得し、詳細ウィンドウを開く"""
        selected_row = self.currentRow()
        if selected_row < 0:
            return
        
        post_id = self.item(selected_row, 0).text().strip()
        self.main_window.show_preview(post_id)

# 機能を増やしたカスタムLineEdit
class CustomLineEdit(QLineEdit):
    returnPressed = pyqtSignal()

    def __init__(self, parent=None):
        super(CustomLineEdit, self).__init__(parent)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            self.returnPressed.emit()
        #return QLineEdit.keyReleaseEvent(self, event)
        super().keyReleaseEvent(event)  # super()で呼び出し
    
    def focusInEvent(self, event):
        super().focusInEvent(event)  # 親クラスの処理を先に実行
        # 少し遅延させてselectAll()を呼び出す
        QTimer.singleShot(0, self.selectAll)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())