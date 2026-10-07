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
