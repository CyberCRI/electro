"""The [extra/contrib] steps that can be used in the flow. Specific to the project."""

import typing
from dataclasses import dataclass
from io import BytesIO
from typing import Type

from .. import FlowConnector
from ..contrib.buttons import Button
from ..contrib.storage_buckets import BaseStorageBucketElement
from ..flow_step import MessageFlowStep
from ..models import BaseModel, File
from ..settings import settings
from ..toolkit.images_storage.universal_image_storage import universal_image_storage
from ..toolkit.loguru_logging import logger
from ..toolkit.templated_i18n import TemplatedString
from .storages import ModelsStorageElement
from .views import ChooseOneOptionView


class ChooseOneModelView(ChooseOneOptionView):
    """Choose one of the models."""

    def __init__(
        self,
        model_to_choose_from: Type[BaseModel],
        options: list[str | Button] | typing.Callable[[], typing.Awaitable[list[str]]] = None,
        answers_storage: BaseStorageBucketElement | None = None,
        **kwargs,
    ):
        """Initialize the view."""
        if not options:
            options = []

        super().__init__(options, answers_storage, **kwargs)

        self.model_to_choose_from: Type[BaseModel] = model_to_choose_from

    async def _get_instances_pks(self) -> list[str]:
        instances: list[BaseModel] = await self.model_to_choose_from.filter(is_active=True, is_deleted=False).all()

        return [str(instance.pk) for instance in instances]

    async def get_static_buttons(self, flow_connector: FlowConnector) -> list[str]:
        return await self._get_instances_pks() + await super().get_static_buttons(flow_connector)

    async def get_or_create_for_connector(
        self,
        flow_connector: FlowConnector,
        dynamic_buttons: list[str | Button] | None = None,
        force_init: bool = False,
        force_get: bool = False,
        from_step_run: bool = False,
    ) -> typing.Self:
        """Get or create the view for the connector."""
        # TODO: [2024-09-11 by Mykola] Make it so that all dynamic views are re-created on each step run
        if from_step_run:
            force_init = True

        return await super().get_or_create_for_connector(
            flow_connector, dynamic_buttons, force_init, force_get, from_step_run
        )

    async def _set_user_answer(self, user_answer: typing.Any):
        """Set the user answer."""
        instance: BaseModel = await self.model_to_choose_from.get_or_none(pk=user_answer)

        return await super()._set_user_answer(instance)


@dataclass
class ChooseOneFromModelsStep(MessageFlowStep):
    """Choose one of the models."""

    model_to_choose_from: Type[BaseModel] = None

    storage_to_save_model_to: ModelsStorageElement = None

    def __post_init__(self):
        if self.model_to_choose_from is None:
            raise ValueError("`model_to_choose_from` is required!")
        if self.storage_to_save_model_to is None:
            raise ValueError("`storage_to_save_model_to` is required!")

        self.view = ChooseOneModelView(
            model_to_choose_from=self.model_to_choose_from,
            answers_storage=self.storage_to_save_model_to,
        )


@dataclass
class AcceptFileStep(MessageFlowStep):
    """Accept a file from the user."""

    storage_to_save_file_url_to: BaseStorageBucketElement | None = None
    storage_to_save_file_object_id_to: BaseStorageBucketElement | None = None

    storage_to_save_saved_file_id_to: BaseStorageBucketElement | None = None

    file_is_required_message: TemplatedString | str = "You need to upload a file."
    file_saved_confirmation_message: TemplatedString | str | None = None

    allow_skip: bool = False

    def __post_init__(self):
        if self.storage_to_save_file_url_to is None:
            raise ValueError("`storage_to_save_file_url_to` is required!")

    async def process_response(self, connector: FlowConnector):
        """Process the response."""
        if not connector.message.attachments:
            if self.allow_skip:
                return await super().process_response(connector)

            return await self.send_message(connector, self.file_is_required_message)

        # Get the first attachment
        attachment = connector.message.attachments[0]

        # Save the file URL
        if self.storage_to_save_file_url_to:
            await self.storage_to_save_file_url_to.set_data(attachment.url)
            logger.info(f"Saved the file URL: {attachment.url=}")

        # Save the File
        if self.storage_to_save_file_object_id_to or self.storage_to_save_saved_file_id_to:
            file_io = BytesIO(await attachment.read())
            file_object_key = await universal_image_storage.upload_image(file_io)

            if self.storage_to_save_file_object_id_to:
                # Save the file object key
                await self.storage_to_save_file_object_id_to.set_data(file_object_key)

                logger.info(f"Saved the file object key: {file_object_key=}")

            if self.storage_to_save_saved_file_id_to:
                # Create the `File` object
                try:
                    file = await File.create(
                        added_by_user_id=connector.user.id,
                        storage_service=settings.STORAGE_SERVICE_ID,
                        storage_file_object_key=file_object_key,
                        file_name=attachment.filename,
                        discord_attachment_id=attachment.id,
                        discord_cdn_url=attachment.url,
                    )

                except Exception as exception:
                    logger.error(f"Failed to save the file: {exception}")
                    return await self.send_message(connector, "Failed to save the file.")

                # Save the file ID
                await self.storage_to_save_saved_file_id_to.set_data(file.pk)

        if self.file_saved_confirmation_message:
            await self.send_message(connector, self.file_saved_confirmation_message)

        return await super().process_response(connector)
