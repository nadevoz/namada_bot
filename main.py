from telegram.ext import Updater, CommandHandler, PicklePersistence, CallbackContext
from telegram import Chat, Update
from rpcwrapper import get_current_epoch, query_proposals, format_notification
import logging
import os

MAX_MESSAGE_LENGTH = 4090
# BOT_TOKEN = '***'

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(msg)s", level=logging.INFO
)

def show_proposal_info(update: Update, context: CallbackContext):
    chat = update.effective_chat
    try:
        target_proposal = context.args[0]
    except Exception as e:
        logging.error(f'Failed to parse argument: {e}')
        context.bot.send_message(text='Failed to parse argument', chat_id=chat.id)
        return

    proposals = context.bot_data.get('proposals_list', set()).copy()
    try:
        current_epoch = get_current_epoch()
    except Exception as e:
        logging.error(f'Failed to get current epoch: {e}')
        context.bot.send_message(text='Failed to get current epoch', chat_id=chat.id)
        return
    text = None
    props = []
    for id, proposal in proposals.items():
        logging.error(f'{id} == {target_proposal}')
        if str(id) == target_proposal:
            try:
                current_epoch = get_current_epoch()
            except Exception as e:
                logging.error(f'Failed to get current epoch: {e}')
                context.bot.send_message(text='Failed to get current epoch', chat_id=chat.id)
                return

            start = int(proposal['Start Epoch'])
            end = int(proposal['End Epoch'])
            content = proposal['Content']
            title = content.get('title')
            if start <= current_epoch and current_epoch <= end:
                title += '(Active)'            
            prop_type = proposal['Type']
            author = proposal['Author']
            abstract = content.get('abstract')
            authors = content.get('authors')
            details = content.get('details')
            props.append(f'#{id} (ends on start of epoch {end+1}): {title}\n\n')
            text = f"Proposal #{id} \nTitle:\n{title}\n\nType: {prop_type}\n\nAbstract:\n{abstract}\n\nAuthor:\n{author}\nEnds on start of epoch {end+1}\n\n"

    if text is None:
        text = f"Proposal not found"

    context.bot.send_message(text=text, chat_id=chat.id)

def list_active_proposals(update: Update, context: CallbackContext):
    chat = update.effective_chat
    proposals = context.bot_data.get('proposals_list', set()).copy()
    try:
        current_epoch = get_current_epoch()
    except Exception as e:
        logging.error(f'Failed to get current epoch: {e}')
        context.bot.send_message(text='Failed to get current epoch', chat_id=chat.id)
        return
    
    props = []
    for id, proposal in proposals.items():
        start = int(proposal['Start Epoch'])
        end = int(proposal['End Epoch'])
        if start <= current_epoch and current_epoch <= end:
            title = proposal['Content'].get('title')
            props.append(f'#{id} (ends on start of epoch {end+1}): {title}\n\n')
    
    msgs = []
    if props:
        props_text = f"Current epoch: {current_epoch}; Active proposals:\n\n"
        for prop in props:
            if len(props_text) + len(prop) > MAX_MESSAGE_LENGTH:
                msgs.append(props_text)
                props_text = prop
            else:
                props_text += prop
        msgs.append(props_text)
    else:
        msgs.append(f"There are no active proposals in the current ({current_epoch}) epoch")
    
    for msg in msgs:
        context.bot.send_message(text=msg, chat_id=chat.id)

def notify_subscribed_users(bot, msgs, subscribed_users):
    for user_id in subscribed_users:
        for msg in msgs:
            try:
                bot.send_message(user_id, msg)
            except Exception as e:
                logging.error(f'Failed to send notification to user {user_id}: {e}')


def start(update: Update, context: CallbackContext) -> None:    
    chat = update.effective_chat
    if chat.type != Chat.PRIVATE:
        return
    
    user_id = update.message.from_user.id
    context.bot_data.setdefault("user_ids", set()).add(user_id)

    text = "Successfully subscribed for SE governance proposals"
    logging.info(f'New user subscribed - {user_id}')

    context.bot.send_message(text=text, chat_id=chat.id)
    list_active_proposals(update, context)


# Function to periodically check for new proposals
def fetch_proposals(context: CallbackContext):
    if not context.bot_data.get("proposals"):
        context.bot_data["proposals"] = set()
    if not context.bot_data.get("notifications"):
        context.bot_data["notifications"] = set()
    if not context.bot_data.get("proposals_list"):
        context.bot_data["proposals_list"] = {}
    
    notifications = context.bot_data["notifications"]
    proposals_list = context.bot_data["proposals_list"]
    proposals = context.bot_data["proposals"]
    current_epoch = get_current_epoch()
    if len(proposals) == 0:
        latest = 0
    else:
        latest = max(proposals)
    
    try:
        new_proposals = query_proposals(latest)
    except Exception as e:
        logging.error(f'Failed to fetch proposals: {e}')
        logging.error(traceback.format_exc())
        return
    
    for prop in new_proposals:
        id = int(prop['Proposal Id'])
        if id not in proposals_list:
            proposals_list[id] = prop
    
    msgs = []
    current_msg = ''
    for id, proposal in proposals_list.items():
        proposals.add(id)
        start = int(proposal['Start Epoch'])
        if id in notifications or start != current_epoch:
            continue

        logging.info(f'sending notifications for prop #{id}')
        notifications.add(id)
        
        notification_text = format_notification(proposal)
        if len(current_msg) + len(notification_text) > MAX_MESSAGE_LENGTH:
            msgs.append(current_msg)
            current_msg = notification_text
        else:
            current_msg += f'{notification_text}\n\n'
        
    if msgs or current_msg:
        msgs.append(current_msg)
        users = context.bot_data.get('user_ids', set()).copy()
        notify_subscribed_users(context.bot, msgs, users)


def main():
    persistence = PicklePersistence(filename='data.pickle')
    bot_token = BOT_TOKEN
    if bot_token is None:
        logging.error('No bot token provided (BOT_TOKEN env var), exiting')
        return
    
    updater = Updater(bot_token, use_context=True, persistence=persistence)

    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("proposals", list_active_proposals))
    dp.add_handler(CommandHandler("get", show_proposal_info))

    updater.start_polling()
    updater.job_queue.run_repeating(fetch_proposals, interval=60, first=3)
    updater.idle()

if __name__ == '__main__':
    main()
