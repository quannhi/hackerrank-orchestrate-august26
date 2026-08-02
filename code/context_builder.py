import os
import pandas as pd


class ContextBuilder:

    def __init__(self, dataset_dir: str = None):
        if dataset_dir is None:
            base_dir = os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            )
            dataset_dir = os.path.join(base_dir, "dataset")

        self.dataset_dir = dataset_dir

        self.messages_df = pd.read_csv(
            os.path.join(dataset_dir, "messages.csv")
        )
        self.users_df = self._load_csv_if_exists("users.csv")
        self.groups_df = self._load_csv_if_exists("groups.csv")
        self.group_members_df = self._load_csv_if_exists("group_members.csv")
        self.business_df = self._load_csv_if_exists("business_accounts.csv")
        self.user_biz_df = self._load_csv_if_exists(
            "user_business_history.csv"
        )
        self.msg_hist_df = self._load_csv_if_exists("message_history.csv")
        self.events_df = self._load_csv_if_exists("message_events.csv")
        self.images_df = self._load_csv_if_exists("images.csv")
        self.voice_notes_df = self._load_csv_if_exists("voice_notes.csv")

    def _load_csv_if_exists(self, filename: str):
        path = os.path.join(self.dataset_dir, filename)
        if os.path.exists(path):
            return pd.read_csv(path)
        return pd.DataFrame()

    def get_message_context(self, message_id: str) -> dict:
        """Builds a comprehensive, security-checked context dictionary for a specific incoming message_id."""
        msg_rows = self.messages_df[
            self.messages_df["message_id"] == message_id
        ]
        if msg_rows.empty:
            raise ValueError(
                f"Message ID {message_id} not found in messages.csv"
            )

        msg = msg_rows.iloc[0].to_dict()
        u_id = msg.get("user_id")
        conv_type = msg.get("conversation_type")
        group_id = msg.get("group_id")
        biz_id = msg.get("business_id")
        sender_user_id = msg.get("sender_user_id")
        media_type = msg.get("media_type")
        media_id = msg.get("media_id")

        context = {
            "message_id": message_id,
            "user_id": u_id,
            "conversation_type": conv_type,
            "created_at": msg.get("created_at"),
            "message_text": (
                msg.get("message_text") if pd.notna(
                    msg.get("message_text")) else ""
            ),
            "forwarded_count": msg.get("forwarded_count", 0),
            "media_type": media_type,
            "media_path": None,
            "security_flags": {
                "is_business_verified": False,
                "domain_mismatch": False,
                "has_prior_user_reports": False,
                "has_prior_user_mutes": False,
            },
            "metrics": {
                "reply_rate": 0.0,
                "dismissal_rate": 0.0,
                "total_past_messages": 0,
            },
            "sender_info": {},
            "user_sender_history": [],
            "evidence_ids": [],
        }

        # 1. Resolve Media Path
        if pd.notna(media_id) and pd.notna(media_type):
            if media_type == "image" and not self.images_df.empty:
                match = self.images_df[self.images_df["image_id"] == media_id]
                if not match.empty:
                    rel_path = match.iloc[0].get(
                        "file_path", f"media/images/{media_id}.png"
                    )
                    context["media_path"] = os.path.join(
                        self.dataset_dir, rel_path
                    )
            elif media_type == "voice" and not self.voice_notes_df.empty:
                match = self.voice_notes_df[
                    self.voice_notes_df["voice_note_id"] == media_id
                ]
                if not match.empty:
                    rel_path = match.iloc[0].get(
                        "file_path", f"media/audio/{media_id}.mp3"
                    )
                    context["media_path"] = os.path.join(
                        self.dataset_dir, rel_path
                    )

        # 2. Business Sender Context & Security Check
        if conv_type == "business" and pd.notna(biz_id):
            if not self.business_df.empty:
                biz_match = self.business_df[
                    self.business_df["business_id"] == biz_id
                ]
                if not biz_match.empty:
                    b_data = biz_match.iloc[0].to_dict()
                    context["sender_info"] = b_data

                    # Security Checks
                    context["security_flags"]["is_business_verified"] = bool(
                        b_data.get("verified", 0) == 1
                    )
                    official_domain = str(
                        b_data.get("official_domain", "")
                    ).lower()
                    sender_domain = str(
                        b_data.get("domain_used_by_sender", "")
                    ).lower()
                    if official_domain and sender_domain:
                        context["security_flags"]["domain_mismatch"] = (
                            official_domain != sender_domain
                        )

            if not self.user_biz_df.empty:
                ub_match = self.user_biz_df[
                    (self.user_biz_df["user_id"] == u_id)
                    & (self.user_biz_df["business_id"] == biz_id)
                ]
                if not ub_match.empty:
                    context["sender_info"]["user_relationship"] = (
                        ub_match.iloc[0].to_dict()
                    )

        # 3. Group Sender Context
        elif conv_type == "group" and pd.notna(group_id):
            if not self.groups_df.empty:
                g_match = self.groups_df[self.groups_df["group_id"] == group_id]
                if not g_match.empty:
                    context["sender_info"] = g_match.iloc[0].to_dict()

            if not self.group_members_df.empty:
                gm_match = self.group_members_df[
                    (self.group_members_df["group_id"] == group_id)
                    & (self.group_members_df["user_id"] == u_id)
                ]
                if not gm_match.empty:
                    context["sender_info"]["user_group_membership"] = (
                        gm_match.iloc[0].to_dict()
                    )

        # 4. History and Past User Behavior Evaluation
        if not self.msg_hist_df.empty:
            if conv_type == "business" and pd.notna(biz_id):
                past_msgs = self.msg_hist_df[
                    (self.msg_hist_df["user_id"] == u_id)
                    & (self.msg_hist_df["business_id"] == biz_id)
                ]
            elif conv_type == "group" and pd.notna(group_id):
                past_msgs = self.msg_hist_df[
                    (self.msg_hist_df["user_id"] == u_id)
                    & (self.msg_hist_df["group_id"] == group_id)
                ]
            elif pd.notna(sender_user_id):
                past_msgs = self.msg_hist_df[
                    (self.msg_hist_df["user_id"] == u_id)
                    & (self.msg_hist_df["sender_user_id"] == sender_user_id)
                ]
            else:
                past_msgs = pd.DataFrame()

            if not past_msgs.empty:
                if not self.events_df.empty:
                    merged = past_msgs.merge(
                        self.events_df,
                        on=["user_id", "message_id"],
                        how="left",
                    )
                else:
                    merged = past_msgs

                total_count = len(merged)
                context["metrics"]["total_past_messages"] = total_count

                if "message_replied" in merged.columns:
                    replies = merged["message_replied"].fillna(0).sum()
                    context["metrics"]["reply_rate"] = float(
                        replies / total_count
                    )

                if "notification_dismissed" in merged.columns:
                    dismissals = (
                        merged["notification_dismissed"].fillna(0).sum()
                    )
                    context["metrics"]["dismissal_rate"] = float(
                        dismissals / total_count
                    )

                if "message_reported" in merged.columns:
                    reports = merged["message_reported"].fillna(0).sum()
                    context["security_flags"][
                        "has_prior_user_reports"
                    ] = bool(reports > 0)

                if "muted_after_message" in merged.columns:
                    mutes = merged["muted_after_message"].fillna(0).sum()
                    context["security_flags"]["has_prior_user_mutes"] = bool(
                        mutes > 0
                    )

                recent_hist = (
                    merged.sort_values("created_at", ascending=False)
                    .head(3)
                    .to_dict("records")
                )
                context["user_sender_history"] = recent_hist
                context["evidence_ids"] = [
                    r["message_id"]
                    for r in recent_hist
                    if "message_id" in r and pd.notna(r["message_id"])
                ]

        return context
