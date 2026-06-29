extends ConfirmationDialog
class_name ConfirmDialog

signal dialog_confirmed()
signal dialog_cancelled()

func _ready() -> void:
	confirmed.connect(_on_confirmed)
	canceled.connect(_on_cancelled)

func show_confirm(
	dialog_title: String = "确认操作",
	message: String = "确定要执行此操作吗？",
	confirm_text: String = "确定",
	cancel_text: String = "取消"
) -> void:
	title = dialog_title
	dialog_text = message
	ok_button_text = confirm_text
	cancel_button_text = cancel_text
	popup_centered()

func _on_confirmed() -> void:
	dialog_confirmed.emit()

func _on_cancelled() -> void:
	dialog_cancelled.emit()
