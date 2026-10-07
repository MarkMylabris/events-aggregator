class EventNotFound(Exception):
    pass


class EventNotPublished(Exception):
    pass


class ProviderUnavailable(Exception):
    pass


class RegistrationClosed(Exception):
    pass


class InvalidSeat(Exception):
    pass


class SeatUnavailable(Exception):
    pass


class RegistrationRejected(Exception):
    """The provider refused the registration for a reason we did not foresee."""


class TicketNotFound(Exception):
    pass


class CancellationRejected(Exception):
    """The provider refused to cancel, e.g. the event is already in the past."""
